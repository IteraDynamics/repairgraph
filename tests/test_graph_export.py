from repairgraph.graph.export_graph import build_graph
from repairgraph.extract.extract_honda_procedure import build_draft_object

from pathlib import Path


FIXTURE_PATH = Path(
    "tests/fixtures/honda_crv_quarter_sample.txt"
)


def load_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_build_graph_contains_nodes_and_edges():
    text = load_fixture()

    draft = build_draft_object(text)

    graph = build_graph(draft)

    assert "nodes" in graph
    assert "edges" in graph

    assert len(graph["nodes"]) > 0
    assert len(graph["edges"]) > 0


def test_graph_contains_replace_component_edge():
    text = load_fixture()

    draft = build_draft_object(text)

    graph = build_graph(draft)

    relationships = [
        edge["relationship"]
        for edge in graph["edges"]
    ]

    assert "replace_component" in relationships
