import json
import sys

from profiler.profiler import ProfileOptions, profile_file
from mapper.mapper import BayanMapper
from matchers.cli import review_uncertain_mappings

def run_pipeline(file_path: str):
    options = ProfileOptions(file=file_path, example_values=3)
    profile = profile_file(options)

    mapper = BayanMapper()
    result = mapper.map(profile)  # {"mapping", "status", "unresolved_columns", "errors", "notes"}

    return profile, result,mapper


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("python main.py data/raw/sales.csv")
        sys.exit(1)

    profile, result,mapper = run_pipeline(sys.argv[1])

    print("===== MAPPING RESULT =====")
    print(json.dumps(result, indent=4, ensure_ascii=False))

    if result["needs_confirmation"]:
        result = review_uncertain_mappings(mapper, result, mapper.schema)

        print("\n===== MAPPING RESULT (après revue) =====")
        print(json.dumps(result, indent=4, ensure_ascii=False))

    if result["status"] == "error":
        print("\n[!] Ce fichier a des erreurs bloquantes et ne peut pas être chargé.")
    elif result["status"] == "needs_review":
        print(f"\n[!] Colonnes encore non résolues : {result['unresolved_columns']}")
    else:
        print("\n[✓] Fichier prêt à être chargé.")