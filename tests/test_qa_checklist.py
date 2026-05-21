from repairgraph.query.loader import load_procedure, load_vehicle_structure, load_all_procedures
from repairgraph.inference.qa_checklist import generate_qa_checklist


def _corpus_without(model: str) -> list[dict]:
    return [p for p in load_all_procedures() if p.get("model") != model]


def test_result_structure():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = generate_qa_checklist(proc)
    assert "checks" in result
    assert "by_category" in result
    assert "by_priority" in result
    assert "total_checks" in result


def test_total_checks_matches_list():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = generate_qa_checklist(proc)
    assert result["total_checks"] == len(result["checks"])


def test_checks_nonempty():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = generate_qa_checklist(proc)
    assert result["total_checks"] > 0


def test_by_priority_covers_all_checks():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = generate_qa_checklist(proc)
    all_from_priority = (
        result["by_priority"].get("critical", [])
        + result["by_priority"].get("high", [])
        + result["by_priority"].get("medium", [])
    )
    assert len(all_from_priority) == result["total_checks"]


def test_critical_checks_for_accord_uhss():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    result = generate_qa_checklist(proc, structure)
    critical = result["by_priority"].get("critical", [])
    assert len(critical) > 0
    categories = [c["category"] for c in critical]
    assert "material_compliance" in categories


def test_no_critical_for_civic_without_uhss():
    proc = load_procedure("Honda", 2025, "Civic")
    structure = load_vehicle_structure("Honda", 2025, "Civic")
    result = generate_qa_checklist(proc, structure)
    critical = result["by_priority"].get("critical", [])
    assert len(critical) == 0


def test_joining_checks_present():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = generate_qa_checklist(proc)
    joining = result["by_category"].get("joining_compliance", [])
    assert len(joining) > 0


def test_component_replacement_checks_present():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = generate_qa_checklist(proc)
    replacements = result["by_category"].get("component_replacement", [])
    assert len(replacements) > 0


def test_corrosion_checks_present():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = generate_qa_checklist(proc)
    corrosion = result["by_category"].get("corrosion_protection", [])
    assert len(corrosion) > 0


def test_dimensional_verification_check_present():
    proc = load_procedure("Honda", 2025, "CR-V")
    result = generate_qa_checklist(proc)
    dimensional = result["by_category"].get("dimensional_verification", [])
    assert len(dimensional) > 0


def test_corpus_gaps_add_completeness_checks():
    proc = load_procedure("Honda", 2025, "Pilot")
    corpus = _corpus_without("Pilot")
    result = generate_qa_checklist(proc, corpus=corpus)
    completeness = result["by_category"].get("completeness", [])
    assert len(completeness) > 0


def test_no_completeness_checks_without_corpus():
    proc = load_procedure("Honda", 2025, "Pilot")
    result = generate_qa_checklist(proc)
    completeness = result["by_category"].get("completeness", [])
    assert len(completeness) == 0


def test_all_checks_have_pass_condition():
    proc = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    corpus = _corpus_without("Accord")
    result = generate_qa_checklist(proc, structure, corpus)
    for check in result["checks"]:
        assert "pass_condition" in check, f"Check missing pass_condition: {check['check']}"


def test_model_metadata_present():
    proc = load_procedure("Honda", 2025, "Accord")
    result = generate_qa_checklist(proc)
    assert result["model"] == "Accord"
    assert result["oem"] == "Honda"
    assert result["year"] == 2025
