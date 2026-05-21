from pathlib import Path

from repairgraph.extract.extract_honda_procedure import (
    extract_structure_nodes,
    extract_joining_methods,
    extract_dependency_phrases,
    build_draft_object,
)


FIXTURE_PATH = Path(
    "tests/fixtures/honda_crv_quarter_sample.txt"
)


def load_fixture() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def test_extract_structure_nodes():
    text = load_fixture()

    nodes = extract_structure_nodes(text)

    phrases = [node["phrase"] for node in nodes]

    assert "rear pillar separator" in phrases
    assert "quarter pillar stiffener" in phrases
    assert "rear side outer panel" in phrases


def test_extract_joining_methods():
    text = load_fixture()

    methods = extract_joining_methods(text)

    assert "spot_weld" in methods
    assert "mag_weld" in methods
    assert "mig_brazing" in methods
    assert "hemming" in methods


def test_extract_dependency_phrases():
    text = load_fixture()

    dependencies = extract_dependency_phrases(text)

    assert len(dependencies) > 0


def test_build_draft_object():
    text = load_fixture()

    draft = build_draft_object(text)

    assert "structure_nodes" in draft
    assert "joining_methods" in draft
    assert "dependency_phrases" in draft
    assert "typed_dependencies" in draft


def test_typed_dependencies_filter_pronouns():
    text = load_fixture()

    draft = build_draft_object(text)

    targets = [
        dependency["target"]
        for dependency in draft["typed_dependencies"]
    ]

    assert "them" not in targets
