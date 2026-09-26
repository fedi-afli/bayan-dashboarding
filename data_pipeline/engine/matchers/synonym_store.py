import json
import re
import unicodedata
from pathlib import Path


BASE_PATH = Path(__file__).resolve().parent

SYNONYMS_PATH = BASE_PATH / "synonyms.json"


def normalize(s: str) -> str:
    """
    Same normalization used everywhere a column/synonym name is compared:
    casefolded, diacritics stripped, anything that isn't a letter/digit
    collapsed to single spaces.

    Letters from any script are kept (Arabic headers must NOT normalize to
    an empty string — that used to make every Arabic column look identical).
    """
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"[\W_]+", " ", s).strip()
    return s


def load_static_synonyms() -> dict:
    """Curated synonyms from synonyms.json."""
    if not SYNONYMS_PATH.exists():
        return {}

    with open(SYNONYMS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("FIELD_SYNONYMS", {})


def _normalized_sets(raw: dict) -> dict:
    return {
        field: {n for n in (normalize(s) for s in syns) if n}
        for field, syns in raw.items()
    }


def get_static_synonyms() -> dict:
    return _normalized_sets(load_static_synonyms())


def is_learnable(source_column: str, static: dict | None = None) -> str | None:
    """
    The normalized key to learn for this column, or None when it shouldn't
    be learned: empty after normalization, or already a curated synonym
    (curated entries always win over what one account confirmed).
    """
    normalized = normalize(source_column)
    if not normalized:
        return None
    static = static if static is not None else get_static_synonyms()
    if any(normalized in syns for syns in static.values()):
        return None
    return normalized
