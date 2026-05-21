from pathlib import Path
import json

from repairgraph.extract.extract_honda_procedure import build_draft_object


OUTPUT_DIR = Path("data/extracted")


def export_draft(text: str, output_name: str):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    draft = build_draft_object(text)

    output_path = OUTPUT_DIR / f"{output_name}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(draft, f, indent=2)

    return output_path


if __name__ == "__main__":
    sample_text_path = Path("tests/fixtures/honda_crv_quarter_sample.txt")

    text = sample_text_path.read_text(encoding="utf-8")

    output_path = export_draft(text, "honda_crv_quarter_draft")

    print(f"Draft exported to: {output_path}")
