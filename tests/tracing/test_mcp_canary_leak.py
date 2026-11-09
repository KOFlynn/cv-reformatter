"""Phase 3, ticket 06: the canary leak test covers the MCP server (ADR-0016).

The harness of ``test_canary_leak`` (the canary Candidate, the four Layouts,
``RealLabeller`` over a fake chat model, every scenario of the labelling
failures and of the retry loop, the detector) is reused; the channel is new:
``reformat_cv`` called through the SDK's in-memory client session, over a
Workspace in a temporary directory, with the source written under a file name
that is itself a canary (a name can be PII). Observed per call: standard error
and every logger, the Tool result (structured content, text, error text) and
the exported spans, in structure mode.

Checked, for every canary and its normalised forms:

* no canary of any class in a Tool result, except the file-name canary in
  ``output_path``. The text rendering states the output path on its first
  line, so that one line is where the same canary may appear (it is the same
  value, in the one field that names a file); the rest of the text, and every
  other structured field, holds none. A tool error is the category and its
  fixed message, exactly, so it holds none;
* no PII or model-echo canary on standard error, and no file name either (the
  log never names the path);
* no canary of any class, the file name included, in any structure-mode span;
* the model key's value nowhere: standard error, the loggers, the Tool result,
  the spans;
* refused calls (not a ``.docx``, outside the Workspace, not found), whose
  path carries a canary: their error text, structured content, standard error
  and spans hold none of it, whether or not the refusal produces spans.

Positive controls: standard error holds content text and the run id, the spans
hold the run id as their trace id, the output path holds the file-name canary,
and the refusals happened with the fixed message.
"""

import contextlib
import io
import json
from dataclasses import dataclass, field

import pytest
from mcp_support import call, summaries
from oracle import Oracle
from test_canary_leak import (
    CONTENT,
    MODEL,
    PII,
    RETRY_SCENARIOS,
    Canaries,
    _canary_candidate,
    _captured,
    _chat,
    _echo,
    _requests,
    _retry_scenarios,
    _scenarios,
    _spans_json,
    leaks,
)
from tracing_support import make_tracer

from cvr.golden import LAYOUTS
from cvr.label import RealLabeller
from cvr.mcp import TOOL_NAME, create_server
from cvr.mcp.server import MESSAGES
from cvr.parse import parse
from cvr.runlog import ErrorCategory
from cvr.template import template_tokens
from cvr.text import tokenise
from cvr.verify.backstops import HEADING_VOCABULARY

# The harvest runs every scenario through all four Layouts and the server,
# about fifteen seconds: the slow suite, so the default run stays short.
pytestmark = pytest.mark.slow

FILE = "filename"  # a canary in the name of the file the caller points at
MODEL_KEY = "sk-ant-canary-key-9876543210abcdef"

OUTPUT_LINE = "Reformatted document written to "


@dataclass
class Call:
    """Everything one tool call put where a reader could see it."""

    path: str
    filename_canary: str
    result: object  # the CallToolResult
    logs: str  # standard output, standard error and every logger
    stderr_lines: str
    spans: list[str] = field(default_factory=list)
    run_id: str | None = None  # the Tool result's, else the summary line's

    @property
    def is_error(self) -> bool:
        return bool(self.result.isError)

    @property
    def text(self) -> str:
        return "\n".join(c.text for c in self.result.content)

    @property
    def error(self) -> str:
        """The error text without the SDK's own ``Error executing tool`` lead."""
        lead = f"Error executing tool {TOOL_NAME}: "
        assert self.text.startswith(lead), self.text
        return self.text.removeprefix(lead)

    @property
    def structured(self) -> dict:
        return self.result.structuredContent or {}

    def without_output_path(self) -> str:
        """The Tool result with the one place the file name may appear taken
        out: the ``output_path`` field and the text's first line."""
        fields = {k: v for k, v in self.structured.items() if k != "output_path"}
        lines = self.text.splitlines()
        rest = [line for line in lines if not line.startswith(OUTPUT_LINE)]
        assert len(lines) - len(rest) == (0 if self.is_error else 1)
        return json.dumps(fields) + "\n" + "\n".join(rest)


def _stderr_run_id(logs: str) -> str | None:
    found = summaries(logs)
    return found[0]["run_id"] if found else None


def _call(root, tracer, exporter, labeller, name: str, canary: str, data=None) -> Call:
    """One ``reformat_cv`` call over ``root/name`` (written first when
    ``data`` is given), observed on every channel."""
    if data is not None:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    server = create_server(labeller, tracer=tracer, workspace=root)
    stderr = io.StringIO()
    # The server writes to the ``sys.stderr`` of the moment: a buffer of our
    # own, so the log lines can be read apart from the loggers' text.
    with _captured() as logs, contextlib.redirect_stderr(stderr):
        result = call(server, path=name)
    text = logs() + "\n" + stderr.getvalue()
    observed = Call(name, canary, result, text, stderr.getvalue())
    observed.spans = _spans_json(tracer, exporter)
    structured = result.structuredContent or {}
    observed.run_id = structured.get("run_id") or _stderr_run_id(stderr.getvalue())
    return observed


@dataclass
class Harvest:
    canaries: Canaries
    sources: dict[str, bytes]
    calls: dict[tuple[str, str], Call]  # (layout, scenario) -> observed
    refused: dict[str, Call]  # category -> observed
    requests: dict[tuple[str, str], list[str]]  # what the fake model received
    root: str
    benign: list[str]


@pytest.fixture(scope="module")
def harvest(tmp_path_factory) -> Harvest:
    canaries = Canaries()
    candidate = _canary_candidate(canaries)
    echo, said = _echo(canaries)
    scenarios = {**_scenarios(echo, said), **_retry_scenarios(echo, said)}
    root = tmp_path_factory.mktemp("workspace")

    calls: dict[tuple[str, str], Call] = {}
    sources: dict[str, bytes] = {}
    requests: dict[tuple[str, str], list[str]] = {}
    refused: dict[str, Call] = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("ANTHROPIC_API_KEY", MODEL_KEY)
        patch.setenv("CVR_MCP_ROOT", str(root))
        for layout in LAYOUTS:
            generated = layout.generate(candidate)
            source = sources[layout.name] = generated.document
            oracle = Oracle(candidate, generated.manifest)
            blocks = parse(source).blocks
            for name, respond in scenarios.items():
                tracer, exporter = make_tracer("structure", tags=["surface=mcp"])
                chat = _chat(respond, oracle, blocks)
                canary = canaries.text(FILE, 2)
                calls[layout.name, name] = _call(
                    root,
                    tracer,
                    exporter,
                    RealLabeller(chat_model=chat),
                    f"{canary} {layout.name}.docx",
                    canary,
                    source,
                )
                requests[layout.name, name] = _requests(chat)

        # Refusals, each with a canary in the path. The labeller must never
        # be reached.
        def never(blocks):
            raise AssertionError("a refused call reached the labeller")

        outside = tmp_path_factory.mktemp("elsewhere")
        (outside / "x.docx").write_bytes(sources[LAYOUTS[0].name])
        paths = {
            "not_docx": ("{c}.txt", sources[LAYOUTS[0].name]),
            "not_found": ("{c}.docx", None),
            "outside_workspace": ("../{c}.docx", None),
        }
        for category, (pattern, data) in paths.items():
            tracer, exporter = make_tracer("structure", tags=["surface=mcp"])
            canary = canaries.text(FILE, 2)
            refused[category] = _call(
                root,
                tracer,
                exporter,
                never,
                pattern.format(c=canary),
                canary,
                data,
            )
        # An absolute path outside the Workspace, canary in a directory name.
        tracer, exporter = make_tracer("structure", tags=["surface=mcp"])
        canary = canaries.text(FILE, 2)
        elsewhere = outside / canary
        elsewhere.mkdir()
        (elsewhere / "cv.docx").write_bytes(sources[LAYOUTS[0].name])
        refused["outside_workspace_absolute"] = _call(
            root, tracer, exporter, never, str(elsewhere / "cv.docx"), canary
        )

    benign = [
        *(c.run_id for c in calls.values() if c.run_id),
        *template_tokens(),
        *HEADING_VOCABULARY,
        "unlocatable conflict removed reformat parse label verify transform render",
        "reformatted docx",
    ]
    return Harvest(canaries, sources, calls, refused, requests, str(root), benign)


def _all(harvest: Harvest):
    return [*harvest.calls.values(), *harvest.refused.values()]


# --- the canaries are sound -------------------------------------------------


def test_the_file_name_canaries_collide_with_nothing_benign(harvest):
    # The temporary Workspace's own path and the layouts' words are not
    # canaries; every canary, the file names' included, is distinct.
    haystack = "\n".join([*harvest.benign, harvest.root])
    assert leaks(haystack, harvest.canaries.of_kind(FILE)) == []


def test_every_call_was_made_over_a_file_name_that_is_a_canary(harvest):
    names = [c.path for c in harvest.calls.values()]
    assert len(names) == len(LAYOUTS) * 11
    for observed in harvest.calls.values():
        assert leaks(observed.path, [observed.filename_canary])


# --- the Tool result --------------------------------------------------------


def test_the_outcomes_are_the_fixed_ones(harvest):
    for (layout, scenario), observed in harvest.calls.items():
        key = (layout, scenario)
        if scenario == "provider-down":
            assert observed.is_error, key
            assert observed.error == (
                f"{ErrorCategory.PROVIDER_UNAVAILABLE.value}: "
                f"{MESSAGES[ErrorCategory.PROVIDER_UNAVAILABLE]}"
            )
        elif scenario == "defect":
            assert observed.is_error, key
            assert observed.error == (
                f"{ErrorCategory.MISCONFIGURED.value}: "
                f"{MESSAGES[ErrorCategory.MISCONFIGURED]}"
            )
        else:
            assert not observed.is_error, key
            expected = (
                "labelling_failed"
                if scenario in {"malformed", "schema-invalid", "refusal"}
                else "ok"
            )
            assert observed.structured["status"] == expected, key
        if scenario in RETRY_SCENARIOS:
            assert observed.structured["retries"] >= 1, key


def test_no_canary_is_in_a_tool_result_but_the_file_name_in_output_path(harvest):
    everything = harvest.canaries.needles
    for key, observed in harvest.calls.items():
        assert leaks(observed.without_output_path(), everything) == [], key
        if not observed.is_error:
            # the output is written beside the source, so its name carries the
            # file-name canary, and in that field only
            assert leaks(observed.structured["output_path"], [observed.filename_canary])
            others = [c for c in everything if c not in harvest.canaries.of_kind(FILE)]
            assert leaks(observed.structured["output_path"], others) == [], key
            assert observed.structured["output_path"] in observed.text


def test_the_tool_result_holds_the_run_id_and_counts(harvest):
    for key, observed in harvest.calls.items():
        if observed.is_error:
            continue
        structured = observed.structured
        assert structured["run_id"] == observed.run_id
        assert structured["input_tokens"] > 0, key
        assert f"Run id: {observed.run_id}" in observed.text


# --- standard error ---------------------------------------------------------


def test_no_pii_canary_and_no_file_name_is_on_standard_error(harvest):
    for key, observed in harvest.calls.items():
        found = leaks(observed.logs, harvest.canaries.of_kind(PII, MODEL, FILE))
        assert found == [], key


def test_standard_error_still_holds_content_text_and_the_run_id(harvest):
    for key, observed in harvest.calls.items():
        assert observed.run_id, key
        assert observed.run_id in observed.logs, key
        if key[1] == "ok":
            assert leaks(observed.logs, harvest.canaries.of_kind(CONTENT)), key


def test_the_log_capture_sees_the_loggers_and_not_only_standard_error(harvest):
    for layout in harvest.sources:
        assert (
            "Processing request of type CallToolRequest"
            in harvest.calls[layout, "defect"].logs
        )


# --- the spans --------------------------------------------------------------


def test_no_canary_is_in_any_exported_span(harvest):
    spans = "\n".join("\n".join(c.spans) for c in _all(harvest))
    assert spans
    assert leaks(spans, harvest.canaries.needles) == []


def test_the_spans_hold_the_run_id_as_their_trace_id(harvest):
    for key, observed in harvest.calls.items():
        spans = [json.loads(s) for s in observed.spans]
        assert spans, key
        assert {s["context"]["trace_id"] for s in spans} == {"0x" + observed.run_id}, (
            key
        )
        names = {s["name"] for s in spans}
        assert {"parse", "label"} <= names, key
        if key[1] not in {"provider-down", "defect"}:
            assert "verify" in names, key
        if key[1] in RETRY_SCENARIOS:
            assert "retry_decision" in names, key


def test_the_source_tokens_that_are_not_the_layouts_own_text_are_in_no_span(harvest):
    spans_tokens = set(tokenise("\n".join("\n".join(c.spans) for c in _all(harvest))))
    own = {
        t for text in (*template_tokens(), *HEADING_VOCABULARY) for t in tokenise(text)
    }
    for layout, source in harvest.sources.items():
        tokens = {
            t for b in parse(source).blocks for t in tokenise(b.text) if len(t) >= 4
        }
        content = tokens - own
        assert content, layout
        assert not (content & spans_tokens), (layout, sorted(content & spans_tokens))


# --- the model key ----------------------------------------------------------


def test_the_model_key_is_nowhere(harvest):
    for key, observed in [*harvest.calls.items(), *harvest.refused.items()]:
        for channel in (
            observed.logs,
            observed.text,
            json.dumps(observed.structured),
            "\n".join(observed.spans),
        ):
            assert leaks(channel, [MODEL_KEY]) == [], key


# --- the refusals -----------------------------------------------------------


def test_a_refused_call_with_a_canary_in_the_path_leaks_none_of_it(harvest):
    assert set(harvest.refused) == {
        "not_docx",
        "not_found",
        "outside_workspace",
        "outside_workspace_absolute",
    }
    for name, observed in harvest.refused.items():
        category = name.removesuffix("_absolute")
        assert observed.is_error, name
        assert observed.error == (f"{category}: {MESSAGES[ErrorCategory(category)]}"), (
            name
        )
        channels = {
            "error": observed.text,
            "structured": json.dumps(observed.structured),
            "stderr": observed.logs,
            "spans": "\n".join(observed.spans),
        }
        for channel, text in channels.items():
            assert leaks(text, harvest.canaries.needles) == [], (name, channel)
        # the call was logged, by its category and a run id, and wrote nothing
        assert observed.run_id and observed.run_id in observed.logs, name
        assert summaries(observed.stderr_lines)[0]["status"] == category, name


def test_what_the_fake_model_received_is_not_a_channel_but_was_exercised(harvest):
    # The provider boundary (ADR-0013) is excluded, as in the API test; the
    # retry scenarios did make retry calls, so the loop was really run.
    for layout in harvest.sources:
        for scenario in RETRY_SCENARIOS:
            assert harvest.requests[layout, scenario], (layout, scenario)
