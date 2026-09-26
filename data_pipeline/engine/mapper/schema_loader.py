import json
from pathlib import Path

DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schemas" / "sales_schema.json"


def load_schema(path=DEFAULT_SCHEMA_PATH):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)
