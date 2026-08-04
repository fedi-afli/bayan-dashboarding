def validate_mapping(mapping, schema, profile=None):
    """
    Retourne (errors, warnings) au lieu d'une seule liste.
    - errors : problèmes sur des champs "core" -> bloquants
    - warnings : mêmes problèmes mais sur des champs "optional"/"metadata"
                 -> signalés mais n'empêchent pas le chargement
    Les colonnes hallucinées restent toujours une erreur (c'est un bug,
    pas une question de données).
    """
    errors = []
    warnings = []

    fields = schema["fields"]
    allowed_fields = set(fields.keys())

    def is_core(field_name):
        return fields.get(field_name, {}).get("importance") == "core"

    if profile is not None:
        real_columns = {col["name"] for col in profile["columns"]}
        hallucinated = [src for src in mapping if src not in real_columns]
        if hallucinated:
            errors.append(f"Mapping references columns not in dataset: {hallucinated}")

    for source, target in mapping.items():
        if target in (None, ""):
            continue
        if target not in allowed_fields:
            errors.append(f"'{target}' (from '{source}') is not in Bayan schema")

    used_targets = {}
    duplicate_targets = {}
    for source, target in mapping.items():
        if target in (None, ""):
            continue
        if target in used_targets:
            duplicate_targets.setdefault(target, [used_targets[target]]).append(source)
        else:
            used_targets[target] = source

    for target, sources in duplicate_targets.items():
        msg = f"Multiple columns mapped to '{target}': {sources}"
        (errors if is_core(target) else warnings).append(msg)

    required = [name for name, v in fields.items() if v["required"]]
    missing = [f for f in required if f not in used_targets]
    for f in missing:
        msg = f"Missing required field: {f}"
        (errors if is_core(f) else warnings).append(msg)

    return errors, warnings