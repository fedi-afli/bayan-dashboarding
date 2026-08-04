import json
def build_mapping_prompt(schema, profile):
    fields_list = "\n".join(
        f"- {name} ({info['type']}{', required' if info['required'] else ''})"
        for name, info in schema["fields"].items()
    )

    columns_list = "\n".join(
        f"- {col['name']} (type: {col['type']}, examples: {col['examples']})"
        for col in profile["columns"]
    )

    prompt = f"""You are mapping dataset columns to a fixed schema.
Dataset column names are often abbreviated or in French. Match them to the
closest schema field by MEANING, not spelling. Never output the source
column name itself as the answer unless it exactly matches a schema field name.

Schema fields:
{fields_list}

Examples of correct mappings (source -> schema field):
- "Art" -> "product_name"
- "Qte" -> "quantity"
- "Montant" -> "revenue"
- "Prix Total" -> "revenue"
- "Date Vente" -> "sale_date"
- "Ref Client" -> null

Now map these dataset columns:
{columns_list}

Output ONE single JSON object with all {len(profile['columns'])} columns as keys,
like this exact structure (using your own values, not these):
{{"Art": "product_name", "Qte": "quantity", "Ref Client": null}}

Respond with ONLY that one JSON object. No extra text, no multiple objects.
"""
    return prompt