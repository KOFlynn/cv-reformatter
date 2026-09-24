"""The pipeline function's own contract: each node once, in order; the
labeller the only thing that could reach an LLM; the Run assembled from
every node's section; and nothing but ``api`` and the eval runner importing
it."""

import ast
from pathlib import Path

import pytest
from oracle import Oracle
from pipeline_support import document

import cvr
from cvr import pipeline
from cvr.models import LabelRun, RemovalRule, Span
from cvr.parse import parse
from cvr.pipeline import reformat

NODES = ["parse", "verify", "transform_content", "render"]


def test_each_node_is_called_once_in_order(monkeypatch):
    calls: list[str] = []
    for name in NODES:
        node = getattr(pipeline, name)

        def recording(*args, _node=node, _name=name):
            calls.append(_name)
            return _node(*args)

        monkeypatch.setattr(pipeline, name, recording)
    doc = document("c04__single-column")
    oracle = Oracle(doc.candidate, doc.manifest)

    def labeller(blocks):
        calls.append("label")
        return oracle(blocks)

    reformat(doc.source, labeller)
    assert calls == ["parse", "label", "verify", "transform_content", "render"]


def test_the_labeller_is_handed_the_parsed_blocks():
    doc = document("c04__text-box")
    seen = []
    oracle = Oracle(doc.candidate, doc.manifest)

    def labeller(blocks):
        seen.append(list(blocks))
        return oracle(blocks)

    reformat(doc.source, labeller)
    assert seen == [parse(doc.source).blocks]


def test_the_run_carries_every_nodes_section():
    doc = document("c04__two-column")
    output, run = reformat(doc.source, Oracle(doc.candidate, doc.manifest))
    parsed = parse(doc.source)
    photo = [r for r in run.removals if r.rule is RemovalRule.PHOTO]
    assert [r.subject for r in photo] == parsed.images
    assert any(isinstance(r.subject, Span) for r in run.removals)
    assert run.normalisations == parsed.normalisations
    assert set(run.ledgers) == {block.id for block in parsed.blocks}
    assert run.residue  # the bullet glyphs, at least
    assert run.date_map
    assert run.label is None  # the oracle records no LabelRun
    assert run.label_failed is False
    assert output.startswith(b"PK")


def test_a_labellers_last_run_becomes_the_runs_label_section():
    doc = document("c04__single-column")
    label_run = LabelRun(
        config={"model": "oracle"},
        prompt_version="p",
        prompt_hash="ph",
        schema_version="s",
        schema_hash="sh",
        content_hash="ch",
    )

    class Recording(Oracle):
        last_run = label_run

    _, run = reformat(doc.source, Recording(doc.candidate, doc.manifest))
    assert run.label == label_run


def test_every_run_has_its_own_id():
    doc = document("c04__single-column")
    oracle = Oracle(doc.candidate, doc.manifest)
    ids = {reformat(doc.source, oracle)[1].run_id for _ in range(2)}
    assert len(ids) == 2


# --- Who may import the pipeline

SRC = Path(cvr.__file__).parent
ALLOWED = ("pipeline/", "api/", "eval/run.py", "eval/run/")


def _imports_pipeline(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = [module, *(f"{module}.{alias.name}" for alias in node.names)]
        else:
            continue
        if any(
            name == "cvr.pipeline" or name.startswith("cvr.pipeline.") for name in names
        ):
            return True
    return False


@pytest.mark.parametrize(
    "path",
    [
        p
        for p in sorted(SRC.rglob("*.py"))
        if not p.relative_to(SRC).as_posix().startswith(ALLOWED)
    ],
    ids=lambda p: p.relative_to(SRC).as_posix(),
)
def test_nothing_but_api_and_the_eval_runner_imports_the_pipeline(path):
    assert not _imports_pipeline(path)
