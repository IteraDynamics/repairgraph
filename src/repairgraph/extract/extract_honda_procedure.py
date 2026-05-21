from pathlib import Path
import re

from repairgraph.taxonomy.structure_nodes import STRUCTURE_NODE_CLASSES
from repairgraph.taxonomy.joining_methods import JOINING_METHODS


DEPENDENCY_PATTERNS = [
    r"inspect.*damage",
    r"replace.*separator",
    r"replace.*stiffener",
    r"replace.*gutter",
]


def normalize_text(text: str) -> str:
    return text.lower().strip()


def extract_structure_nodes(text: str) -> list[dict]:
    text = normalize_text(text)

    results = []

    for node_class, phrases in STRUCTURE_NODE_CLASSES.items():
        for phrase in phrases:
            if phrase.lower() in text:
                results.append(
                    {
                        "class": node_class,
                        "phrase": phrase,
                    }
                )

    return results


def extract_joining_methods(text: str) -> list[str]:
    text = normalize_text(text)

    results = []

    for canonical_name, phrases in JOINING_METHODS.items():
        for phrase in phrases:
            if phrase.lower() in text:
                results.append(canonical_name)
                break

    return sorted(set(results))


def extract_dependency_phrases(text: str) -> list[str]:
    text = normalize_text(text)

    matches = []

    for pattern in DEPENDENCY_PATTERNS:
        found = re.findall(pattern, text)
        matches.extend(found)

    return matches


def build_draft_object(text: str) -> dict:
    return {
        "structure_nodes": extract_structure_nodes(text),
        "joining_methods": extract_joining_methods(text),
        "dependency_phrases": extract_dependency_phrases(text),
    }


if __name__ == "__main__":
    sample_path = Path("sample_procedure.txt")

    if sample_path.exists():
        text = sample_path.read_text(encoding="utf-8")

        draft = build_draft_object(text)

        print(draft)
