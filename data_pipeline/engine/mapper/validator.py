def validate_mapping(mapping, schema, profile=None):
    """
    Returns (errors, warnings).
    - errors block loading: unknown columns/fields, two columns on the same
      field, or nothing mapped at all.
    - warnings don't: a missing "required" field just means the charts that
      need it are skipped, the rest of the dashboard still works.
    """
    errors = []
    warnings = []

    fields = schema["fields"]
    allowed_fields = set(fields.keys())

    def label(name):
        return fields.get(name, {}).get("label", name)

    if profile is not None:
        real_columns = {col["name"] for col in profile["columns"]}
        unknown = [src for src in mapping if src not in real_columns]
        if unknown:
            errors.append(f"These columns aren't in the file: {unknown}")

    for source, target in mapping.items():
        if target in (None, ""):
            continue
        if target not in allowed_fields:
            errors.append(f"'{target}' (from '{source}') is not a known field")

    used_targets = {}
    for source, target in mapping.items():
        if target in (None, ""):
            continue
        used_targets.setdefault(target, []).append(source)

    for target, sources in used_targets.items():
        if len(sources) > 1:
            errors.append(
                f"{', '.join(repr(s) for s in sources)} are all set to '{label(target)}' — pick only one"
            )

    if not used_targets:
        errors.append("No column is matched to a field yet — map at least one column.")

    required = [name for name, v in fields.items() if v.get("required")]
    for f in required:
        if f not in used_targets:
            warnings.append(f"No column for '{label(f)}' — charts that need it will be skipped.")

    return errors, warnings
