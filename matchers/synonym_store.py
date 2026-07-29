import json
import re
import unicodedata
from pathlib import Path

from .synonyms import FIELD_SYNONYMS

LEARNED_PATH = Path("matchers/learned_synonyms.json")


def normalize(s: str) -> str:
    """
    Same normalization used everywhere a column/synonym name is compared:
    lowercase, accents stripped, non-alphanumeric collapsed to single spaces.
    Keeping this in one place avoids "Prix Unitaire" vs "prix unitaire"
    style mismatches between the static synonym file and live column names.
    """
    s = s.strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def load_learned_synonyms() -> dict:
    if not LEARNED_PATH.exists():
        return {}
    with open(LEARNED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_merged_synonyms() -> dict:
    """
    Static curated synonyms (matchers/synonyms.py) + runtime-confirmed ones
    (matchers/learned_synonyms.json), merged and normalized. The static
    file is never mutated by the app; only the learned file grows.
    """
    merged = {field: {normalize(s) for s in syns} for field, syns in FIELD_SYNONYMS.items()}

    for field, syns in load_learned_synonyms().items():
        merged.setdefault(field, set()).update(normalize(s) for s in syns)

    return merged


def confirm_synonym(source_column: str, target_field: str):
    """
    Record a client-confirmed source-column -> field mapping so it's
    matched deterministically next time, with no LLM call needed.
    """
    normalized = normalize(source_column)

    learned = load_learned_synonyms()
    existing = learned.setdefault(target_field, [])
    if normalized not in existing:
        existing.append(normalized)

    with open(LEARNED_PATH, "w", encoding="utf-8") as f:
        json.dump(learned, f, indent=2, ensure_ascii=False)