"""
Terminal version of the pipeline: upload -> review in the terminal -> build.
Goes through the same engine interface as the API, so the dashboard shows
up in the web app for that account. Operator tool: no credits are charged.

    python main.py path/to/sales.csv [--account <account id>]
"""

import argparse
import json
import sys
from pathlib import Path

from engine.mapper.mapper import BayanMapper
from engine.matchers.confirmation import review_uncertain_mappings
from engine.service import Engine, EngineError, MappingInvalid
from saas.accounts import DEFAULT_ACCOUNT_ID

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file")
    parser.add_argument("--account", default=DEFAULT_ACCOUNT_ID, help="account (tenant) id to create the dashboard in")
    args = parser.parse_args()

    mapper = BayanMapper()
    engine = Engine(mapper, UPLOAD_DIR, 200 * 1024 * 1024)

    try:
        with open(args.file, "rb") as f:
            review = engine.ingest_upload(args.account, Path(args.file).name, f)
    except (OSError, EngineError) as e:
        print(f"[✗] {e}")
        return 1

    result = review["result"]
    print("===== MAPPING RESULT =====")
    print(json.dumps({k: v for k, v in result.items() if k != "columns"}, indent=4, ensure_ascii=False))
    if result["needs_confirmation"]:
        result = review_uncertain_mappings(mapper, result, mapper.schema)

    try:
        overview = engine.build_dashboard(args.account, review["dataset_id"], result["mapping"])
    except MappingInvalid as e:
        print("\n[!] Ce fichier a des erreurs bloquantes et ne peut pas être chargé :")
        for err in e.errors:
            print(f"    - {err}")
        return 1
    except EngineError as e:
        print(f"[✗] {e}")
        return 1

    print(f"\n[✓] {overview['row_count']} lignes chargées — dashboard {overview['id']}")
    for c in overview["charts"]:
        hidden = " [masqué]" if c["name"] in overview["hidden_charts"] else ""
        print(f"    - {c['title']} ({c['chart_type']}){hidden}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
