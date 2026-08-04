import json
import sys
import os

import pandas as pd
from psycopg2.extras import execute_values

from profiler.profiler import ProfileOptions, profile_file
from mapper.mapper import BayanMapper
from matchers.confirmation import review_uncertain_mappings
from mapper.sql_schema_generator import load_schema, generate_create_table_sql, save_sql_file
from db import execute_sql, get_connection
from rules import resolve_charts_from_mapping


def apply_mapping(dataset: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Keep only the columns that were successfully mapped, and rename them
    to their target schema field names. Columns that aren't in `mapping`
    (i.e. never resolved to a schema field) are dropped.
    """
    mapped_columns = [col for col in dataset.columns if col in mapping]

    if not mapped_columns:
        raise ValueError("No columns in the dataset match the mapping — nothing to load.")

    cleaned = dataset[mapped_columns].copy()
    cleaned = cleaned.rename(columns=mapping)

    return cleaned


def load_dataframe_to_postgres(df: pd.DataFrame, table_name: str) -> None:
    """
    Bulk-insert a DataFrame into an existing Postgres table using
    psycopg2's execute_values (fast multi-row INSERT).
    Assumes `generate_create_table_sql` / `execute_sql` already created
    the table — this only inserts rows.
    """
    if df.empty:
        print("[!] Dataset vide après mapping — rien à charger.")
        return

    columns = list(df.columns)
    # Replace pandas/NumPy NaN with None so psycopg2 writes SQL NULL
    rows = [
        tuple(None if pd.isna(v) else v for v in row)
        for row in df.itertuples(index=False, name=None)
    ]

    insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES %s"

    conn = get_connection()
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            execute_values(cur, insert_sql, rows)
        conn.commit()
        print(f"[✓] {len(rows)} lignes insérées dans '{table_name}'")
    except Exception as e:
        conn.rollback()
        print(f"[✗] Échec de l'insertion dans '{table_name}': {e}")
        raise
    finally:
        conn.close()


def run_pipeline(file_path: str):
    options = ProfileOptions(file=file_path, example_values=3)
    profile, dataset = profile_file(options)

    mapper = BayanMapper()
    result = mapper.map(profile)  # {"mapping", "status", "unresolved_columns", "errors", "notes"}

    return profile, result, mapper, dataset


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("python main.py data/raw/sales.csv")
        sys.exit(1)

    profile, result, mapper, dataset = run_pipeline(sys.argv[1])

    print("===== MAPPING RESULT =====")
    print(json.dumps(result, indent=4, ensure_ascii=False))

    if result["needs_confirmation"]:
        result = review_uncertain_mappings(mapper, result, mapper.schema)

        print("\n===== MAPPING RESULT (après revue) =====")
        print(json.dumps(result, indent=4, ensure_ascii=False))

    if result["status"] == "error":
        print("\n[!] Ce fichier a des erreurs bloquantes et ne peut pas être chargé.")
        sys.exit(1)

    elif result["status"] == "needs_review":
        print(f"\n[!] Colonnes encore non résolues : {result['unresolved_columns']}")

    print("\n[✓] Fichier prêt à être chargé.")

    # Create output directory if it doesn't exist
    os.makedirs("output", exist_ok=True)

    # Save only the mapping
    mapping_path = "output/mapping.json"
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(result["mapping"], f, indent=4, ensure_ascii=False)

    schema = load_schema("schemas/sales_schema.json")  # adjust path if schema.json lives elsewhere
    create_table_sql = generate_create_table_sql(
        schema, mapping=result["mapping"], table_name="sales"
    )

    # Keep a copy on disk for reference / version control
    sql_path = "output/create_table.sql"
    save_sql_file(create_table_sql, sql_path)
    print(f"[✓] SQL creation script saved to {sql_path}")

    # Create the table directly inside bayan_db
    execute_sql(create_table_sql)

    # Rename mapped columns and drop unmapped ones, then load the rows
    cleaned_dataset = apply_mapping(dataset, result["mapping"])

    load_dataframe_to_postgres(cleaned_dataset, table_name="sales")

    # Resolve which charts apply given the fields that actually made it into
    # the table (i.e. the mapping's target field names, not the raw columns)
    charts = resolve_charts_from_mapping(result["mapping"])

    charts_path = "output/charts.json"
    with open(charts_path, "w", encoding="utf-8") as f:
        json.dump(charts, f, indent=4, ensure_ascii=False)

    print(f"[✓] {len(charts)} chart(s) résolu(s) et sauvegardé(s) dans {charts_path}")
    for c in charts:
        print(f"    - {c['title']} ({c['chart_type']})")