"""
Which schema field types a profiled column type can plausibly hold.

Used to reject matches that can't be right no matter how similar the
names are (e.g. a datetime column mapped to the integer `sale_quarter`).
"""

# profiler column type -> schema field types it may map to
COMPATIBLE = {
    "integer": {"integer", "float", "boolean", "string"},  # ids / postal codes arrive as ints
    "float": {"float", "integer", "string"},                # ints with blanks become floats
    "string": {"string", "date", "boolean"},
    "datetime": {"date"},
    "boolean": {"boolean"},
    "empty": set(),
}


def is_compatible(column_type: str, field_type: str) -> bool:
    return field_type in COMPATIBLE.get(column_type, {"string"})


def compatible_fields(column_type: str, schema: dict, candidates=None) -> list[str]:
    names = candidates if candidates is not None else schema["fields"].keys()
    return [f for f in names if is_compatible(column_type, schema["fields"][f]["type"])]
