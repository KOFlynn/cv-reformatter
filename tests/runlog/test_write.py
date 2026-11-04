"""The writer writes to the stream it is given and to nothing else: the API
gives it standard output, the MCP server standard error (whose standard
output is the protocol's channel)."""

import inspect
import io
import sys

from cvr.runlog import request_lines, write_lines


def test_the_lines_go_to_the_given_stream_one_per_line():
    stream = io.StringIO()
    lines = request_lines("abc", 415, error="not a .docx")
    write_lines(lines, stream)
    assert stream.getvalue() == lines[0] + "\n"


def test_nothing_reaches_standard_output_when_given_another_stream(capsys):
    write_lines(request_lines("abc", 415, error="not a .docx"), sys.stderr)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert '"run_id":"abc"' in captured.err


def test_the_stream_is_required():
    stream = inspect.signature(write_lines).parameters["stream"]
    assert stream.default is inspect.Parameter.empty
