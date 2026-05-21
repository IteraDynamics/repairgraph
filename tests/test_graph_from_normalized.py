import pytest
from repairgraph.query.loader import (
    load_procedure,
    load_vehicle_structure,
    load_all_procedures,
    load_all_vehicle_structures,
)
from repairgraph.graph.build_from_normalized import (
    build_graph_from_normalized,
    build_multi_vehicle_graph,
)


def test_build_graph_from_crv_procedure():
    proc = load_procedure("Honda", 2025, "CR-V")
    structure = load_vehicle_structure("Honda", 2025, "CR-V")
    graph = build_graph_from_normalized(proc, structure)

    assert "nodes" in graph
    assert "edges" in graph
    assert len(graph["nodes"]) > 0
    assert len(graph["edges"]) > 0


def test_graph_contains_operation_node():
    proc = load_procedure("Honda", 2025, "CR-V")
    graph = build_graph_from_normalized(proc)
    node_types = [n["type"] for n in graph["nodes"]]
    assert "operation" in node_types


def test_graph_contains_joining_method_edges():
    proc = load_procedure("Honda", 2025, "CR-V")
    graph = build_graph_from_normalized(proc)
    relationships = [e["relationship"] for e in graph["edges"]]
    assert "uses_joining_method" in relationships


def test_graph_contains_corrosion_edges():
    proc = load_procedure("Honda", 2025, "CR-V")
    graph = build_graph_from_normalized(proc)
    relationships = [e["relationship"] for e in graph["edges"]]
    assert "requires_corrosion_protection" in relationships


def test_graph_contains_sectioning_edges():
    proc = load_procedure("Honda", 2025, "CR-V")
    graph = build_graph_from_normalized(proc)
    relationships = [e["relationship"] for e in graph["edges"]]
    assert "sections_at" in relationships


def test_graph_contains_material_nodes_when_structure_provided():
    proc = load_procedure("Honda", 2025, "CR-V")
    structure = load_vehicle_structure("Honda", 2025, "CR-V")
    graph = build_graph_from_normalized(proc, structure)
    node_types = [n["type"] for n in graph["nodes"]]
    assert "material_spec" in node_types


def test_graph_meta_contains_model_info():
    proc = load_procedure("Honda", 2025, "CR-V")
    graph = build_graph_from_normalized(proc)
    assert graph["meta"]["model"] == "CR-V"
    assert graph["meta"]["oem"] == "Honda"
    assert graph["meta"]["year"] == 2025


def test_build_multi_vehicle_graph():
    procedures = load_all_procedures()
    structures = load_all_vehicle_structures()

    structure_by_model = {s["model"]: s for s in structures}
    pairs = [(proc, structure_by_model.get(proc["model"])) for proc in procedures]

    graph = build_multi_vehicle_graph(pairs)

    assert "nodes" in graph
    assert "edges" in graph
    assert "meta" in graph
    assert graph["meta"]["type"] == "multi_vehicle_graph"
    assert len(graph["meta"]["procedures"]) >= 5


def test_multi_vehicle_graph_contains_shared_component_edges():
    procedures = load_all_procedures()
    structures = load_all_vehicle_structures()

    structure_by_model = {s["model"]: s for s in structures}
    pairs = [(proc, structure_by_model.get(proc["model"])) for proc in procedures]

    graph = build_multi_vehicle_graph(pairs)

    relationships = [e["relationship"] for e in graph["edges"]]
    assert "shares_component" in relationships


def test_multi_vehicle_graph_deduplicates_nodes():
    procedures = load_all_procedures()
    structures = load_all_vehicle_structures()

    structure_by_model = {s["model"]: s for s in structures}
    pairs = [(proc, structure_by_model.get(proc["model"])) for proc in procedures]

    graph = build_multi_vehicle_graph(pairs)

    node_ids = [n["id"] for n in graph["nodes"]]
    assert len(node_ids) == len(set(node_ids))
