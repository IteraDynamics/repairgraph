from pathlib import Path

from repairgraph.extract.extract_honda_procedure import build_draft_object
from repairgraph.graph.export_graph import build_graph
from repairgraph.graph.export_mermaid import build_mermaid


FIXTURE_PATH = Path(
    "tests/fixtures/honda_crv_quarter_sample.txt"
)


def load_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_build_mermaid_contains_graph_header():
    text = load_fixture()

    draft = build_draft_object(text)
    graph = build_graph(draft)

    mermaid = build_mermaid(graph)

    assert "graph TD" in mermaid


def test_build_mermaid_contains_relationships():
    text = load_fixture()

    draft = build_draft_object(text)
    graph = build_graph(draft)

    mermaid = build_mermaid(graph)

    assert "replace_component" in mermaid
    assert "inspect_if_damaged" in mermaid
