import json
import sys
import os 

from profiler.profiler import ProfileOptions, profile_file
from mapper.mapper import BayanMapper
from matchers.confirmation import review_uncertain_mappings
from mapper.sql_schema_generator import load_schema, generate_create_table_sql, save_sql_file

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

    profile, result, mapper = run_pipeline(sys.argv[1])

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

    
    print("\n[✓] Fichier prêt à être chargé.")

    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)

    # Save only the mapping
    mapping_path = "output/mapping.json"

    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(result["mapping"], f, indent=4, ensure_ascii=False)

    schema = load_schema("schemas/sales_schema.json")
    create_table_sql = generate_create_table_sql(
        schema, mapping=result["mapping"], table_name="sales"
    )

    sql_path = "output/create_table.sql"
    save_sql_file(create_table_sql, sql_path)
    print(f"[✓] SQL creation script saved to {sql_path}")