def validate_mapping(mapping, schema, profile=None):
    allowed_fields = set(schema["fields"].keys())

    if profile is not None:
        real_columns = {col["name"] for col in profile["columns"]}
        hallucinated = [src for src in mapping if src not in real_columns]
        if hallucinated:
            raise Exception(f"Mapping references columns not in dataset: {hallucinated}")

    for source, target in mapping.items():
        if target in (None, ""):
            continue
        if target not in allowed_fields:
            raise Exception(f"'{target}' (from '{source}') is not in Bayan schema")

    used_targets = {}
    for source, target in mapping.items():
        if target in (None, ""):
            continue
        if target in used_targets:
            raise Exception(
                f"Both '{used_targets[target]}' and '{source}' mapped to '{target}'"
            )
        used_targets[target] = source

    required = [name for name, v in schema["fields"].items() if v["required"]]
    missing = [f for f in required if f not in used_targets]
    if missing:
        raise Exception(f"Missing required fields: {missing}")

    return True