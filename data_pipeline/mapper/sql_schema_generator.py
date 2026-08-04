import json

SQL_TYPE_MAPPING = {
    "string": "VARCHAR(255)",
    "integer": "INTEGER",
    "float": "FLOAT",
    "date": "DATE",
    "boolean": "BOOLEAN",
}

def load_schema(schema_path: str) -> dict:
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_create_table_sql(schema: dict, mapping: dict, table_name: str = "sales") -> str:
    """
    Build a CREATE TABLE statement containing only the schema fields
    that were actually matched in `mapping` (result["mapping"]).

    mapping: dict like {"ticketNumber": "order_line_number", "itemDescription": "product_name"}
             i.e. {source_column: schema_field_name}
    """
    fields = schema["fields"]

    # The set of schema field names that were actually mapped to source columns
    mapped_field_names = set(mapping.values())

    lines = []
    for field_name in mapped_field_names:
        field_def = fields.get(field_name)
        if field_def is None:
            # mapping points to a field name that doesn't exist in the schema — skip or raise
            print(f"[!] Warning: '{field_name}' in mapping not found in schema, skipping")
            continue

        sql_type = SQL_TYPE_MAPPING.get(field_def["type"], "VARCHAR(255)")
        nullability = "NOT NULL" if field_def.get("required") else "NULL"
        lines.append(f"    {field_name} {sql_type} {nullability}")

    columns_sql = ",\n".join(lines)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n{columns_sql}\n);"

def save_sql_file(sql: str, output_path: str = "output/create_table.sql"):
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(sql)