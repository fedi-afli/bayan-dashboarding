import json
import re
import unicodedata
from pathlib import Path


BASE_PATH = Path("matchers")

SYNONYMS_PATH = BASE_PATH / "synonyms.json"
LEARNED_PATH = BASE_PATH / "learned_synonyms.json"


def normalize(s: str) -> str:
    """
    Same normalization used everywhere a column/synonym name is compared:
    lowercase, accents stripped, non-alphanumeric collapsed to single spaces.
    Keeping this in one place avoids mismatches between the synonym file
    and live column names.
    """
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def load_static_synonyms() -> dict:
    """
    Load curated synonyms from synonyms.json.
    """
    if not SYNONYMS_PATH.exists():
        return {}

    with open(SYNONYMS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("FIELD_SYNONYMS", {})


def load_learned_synonyms() -> dict:
    """
    Load runtime-confirmed synonyms.
    """
    if not LEARNED_PATH.exists():
        return {}

    with open(LEARNED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_merged_synonyms() -> dict:
    """
    Static curated synonyms (matchers/synonyms.json) +
    runtime-confirmed ones (matchers/learned_synonyms.json),
    merged and normalized.

    The static file is never mutated.
    Only the learned file grows.
    """
    static_synonyms = load_static_synonyms()

    merged = {
        field: {normalize(s) for s in syns}
        for field, syns in static_synonyms.items()
    }

    for field, syns in load_learned_synonyms().items():
        merged.setdefault(field, set()).update(
            normalize(s) for s in syns
        )

    return merged


def confirm_synonym(source_column: str, target_field: str):
    """
    Record a client-confirmed source-column -> field mapping so it is
    matched deterministically next time, without requiring an LLM call.
    """
    normalized = normalize(source_column)

    learned = load_learned_synonyms()

    existing = learned.setdefault(target_field, [])

    if normalized not in existing:
        existing.append(normalized)

    LEARNED_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(LEARNED_PATH, "w", encoding="utf-8") as f:
        json.dump(
            learned,
            f,
            indent=2,
            ensure_ascii=False
        )