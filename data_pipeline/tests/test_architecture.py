"""The seam between the data engine and the SaaS layer, enforced."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMPORT = re.compile(r"^\s*(?:from|import)\s+([\w.]+)", re.M)


def imports_of(package: str):
    for path in (ROOT / package).rglob("*.py"):
        for module in IMPORT.findall(path.read_text(encoding="utf-8")):
            yield path.relative_to(ROOT), module


def test_engine_never_imports_the_saas_layer():
    offenders = [(p, m) for p, m in imports_of("engine") if m == "saas" or m.startswith("saas.")]
    assert offenders == []


def test_saas_only_uses_the_engine_facade():
    offenders = [(p, m) for p, m in imports_of("saas")
                 if (m == "engine" or m.startswith("engine.")) and m != "engine.service"]
    assert offenders == []


def test_saas_never_touches_engine_tables():
    for path in (ROOT / "saas").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "bayan_datasets" not in text and "learned_synonyms" not in text, path
