import re


def normalize_target(text: str) -> str:
    cleaned = text.strip().lower()
    cleaned = cleaned.replace("the ", "")
    cleaned = cleaned.replace(" and ", " ")
    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    return cleaned.strip("_")


def split_component_list(text: str) -> list[str]:
    text = text.strip().rstrip(".")
    text = text.replace(", and ", ", ")
    text = text.replace(" and ", ", ")
    parts = [part.strip() for part in text.split(",")]
    return [part for part in parts if part]


def extract_typed_dependencies(text: str) -> list[dict]:
    dependencies = []

    replace_matches = re.findall(
        r"replace\s+(?:the\s+)?([^\.]+)",
        text,
        flags=re.IGNORECASE,
    )

    for match in replace_matches:
        for component in split_component_list(match):
            dependencies.append(
                {
                    "type": "replace_component",
                    "target": normalize_target(component),
                    "raw": component,
                }
            )

    inspect_matches = re.findall(
        r"check\s+(?:the\s+)?([^\.]+?)\s+position\s+for\s+damage",
        text,
        flags=re.IGNORECASE,
    )

    for match in inspect_matches:
        dependencies.append(
            {
                "type": "inspect_if_damaged",
                "target": normalize_target(match),
                "raw": match,
            }
        )

    return dependencies
