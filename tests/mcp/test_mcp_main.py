"""``python -m cvr.mcp`` as a process: the stdio handshake, the tool list,
a clean stdout and exit, and the start-up refusals. No ``reformat_cv`` call
is made and no model key is in the environment."""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO

import pytest

# Each test starts a Python process that imports the SDK and the pipeline,
# about ten seconds apiece: the slow suite, so the default run does not grow by them.
pytestmark = pytest.mark.slow

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(**extra: str) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("CVR_", "ANTHROPIC_", "LANGFUSE_", "AZURE_"))
    }
    env.update(extra)
    return env


def _start(env: dict[str, str]) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "cvr.mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=REPO_ROOT,
        env=env,
    )


def _drain(stream: IO[str], into: queue.Queue) -> None:
    for line in stream:
        into.put(line)
    into.put(None)


def test_handshake_tool_list_clean_stdout_and_exit_on_eof(tmp_path):
    # Closing stdin is the client's shutdown, and on it the SDK cancels any
    # request still in flight, so a response not yet written is dropped. A
    # client waits for each response before it sends the next request and
    # before it closes stdin; writing all three and closing at once lost the
    # tools/list response about one run in six.
    # One 60 s budget for the whole exchange, as the single communicate call
    # had: every wait below gets what is left of it.
    proc = _start(_env(CVR_MCP_ROOT=str(tmp_path)))
    deadline = time.monotonic() + 60
    out: queue.Queue[str | None] = queue.Queue()
    err: queue.Queue[str | None] = queue.Queue()
    threading.Thread(target=_drain, args=(proc.stdout, out), daemon=True).start()
    threading.Thread(target=_drain, args=(proc.stderr, err), daemon=True).start()
    received: list[str] = []

    def left() -> float:
        return max(deadline - time.monotonic(), 0)

    def send(*messages: dict) -> None:
        proc.stdin.write("".join(json.dumps(m) + "\n" for m in messages))
        proc.stdin.flush()

    def await_response(request_id: int) -> None:
        while True:
            line = out.get(timeout=left())
            assert line is not None, f"stdout closed before response {request_id}"
            received.append(line)
            if line.strip() and json.loads(line).get("id") == request_id:
                return

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            }
        )
        await_response(1)
        send(
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        await_response(2)
        proc.stdin.close()
        proc.wait(timeout=left())
        while (line := out.get(timeout=left())) is not None:
            received.append(line)
        stderr = "".join(iter(lambda: err.get(timeout=left()), None))
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    assert proc.returncode == 0, stderr[-3000:]

    lines = [line for line in received if line.strip()]
    parsed = [json.loads(line) for line in lines]
    assert all(m.get("jsonrpc") == "2.0" for m in parsed), lines
    by_id = {m["id"]: m for m in parsed if "id" in m}
    assert "serverInfo" in by_id[1]["result"]
    assert [t["name"] for t in by_id[2]["result"]["tools"]] == ["reformat_cv"]


@pytest.mark.parametrize(
    ("env", "named"),
    [
        ({}, "CVR_MCP_ROOT"),
        ({"CVR_MCP_ROOT": ""}, "CVR_MCP_ROOT"),
        ({"CVR_MCP_ROOT": "no-such-directory"}, "CVR_MCP_ROOT"),
        ({"CVR_RETRY_MAX": "many"}, "CVR_RETRY_MAX"),
        ({"CVR_RETRY_MAX": "-1"}, "CVR_RETRY_MAX"),
    ],
)
def test_it_refuses_to_start(env, named, tmp_path):
    env = dict(env)
    if "CVR_RETRY_MAX" in env:
        env["CVR_MCP_ROOT"] = str(tmp_path)
    proc = _start(_env(**env))
    stdout, stderr = proc.communicate("", timeout=60)
    assert proc.returncode == 2
    assert stdout == ""
    assert named in stderr
    assert "Traceback" not in stderr


def test_a_file_is_not_a_workspace(tmp_path):
    a_file = tmp_path / "file.txt"
    a_file.write_text("x")
    proc = _start(_env(CVR_MCP_ROOT=str(a_file)))
    stdout, stderr = proc.communicate("", timeout=60)
    assert proc.returncode == 2
    assert stdout == ""
    assert "CVR_MCP_ROOT" in stderr
