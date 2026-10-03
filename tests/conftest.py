import json
from pathlib import Path

EXAMPLES_DIR = Path(__file__).parent / "fixtures" / "examples"


def load_example(name: str) -> dict:
    return json.loads((EXAMPLES_DIR / f"{name}.json").read_text())
