"""The pipeline runs as a LangGraph graph of the five Phase 1 nodes."""

import pytest
from pipeline_support import document

from cvr.label.errors import ProviderUnavailable
from cvr.pipeline import _build_graph, reformat


def test_the_graph_is_the_five_nodes_in_a_line():
    graph = _build_graph(lambda blocks: None).get_graph()
    edges = {(e.source, e.target) for e in graph.edges}
    assert edges == {
        ("__start__", "parse"),
        ("parse", "label"),
        ("label", "verify"),
        ("verify", "transform"),
        ("transform", "render"),
        ("render", "__end__"),
    }


def test_a_labeller_error_reaches_the_caller_unchanged():
    def unavailable(blocks):
        raise ProviderUnavailable("down")

    with pytest.raises(ProviderUnavailable):
        reformat(document("c04__single-column").source, unavailable)
