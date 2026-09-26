from engine.mapper.schema_loader import load_schema
from engine.mapper.validator import validate_mapping
from engine.matchers.synonym_store import is_learnable, normalize
from engine.matchers.type_compat import compatible_fields, is_compatible

SCHEMA = load_schema()


def test_normalize_keeps_arabic_letters():
    assert normalize("المنتج") == "المنتج"
    assert normalize("المدينة") != normalize("المنتج")
    assert normalize("  Désignation_Article ") == "designation article"


def test_normalize_strips_arabic_diacritics():
    assert normalize("المُنْتَج") == "المنتج"


def test_datetime_column_cannot_map_to_integer_field():
    assert not is_compatible("datetime", "integer")
    assert "sale_quarter" not in compatible_fields("datetime", SCHEMA)
    assert "sale_date" in compatible_fields("datetime", SCHEMA)


def test_validator_rejects_unknown_field_names():
    # this is what keeps arbitrary strings out of generated SQL
    errors, _ = validate_mapping({"Montant": "revenue) SELECT 1; --"}, SCHEMA)
    assert any("not a known field" in e for e in errors)


def test_validator_rejects_duplicate_targets():
    errors, _ = validate_mapping({"a": "revenue", "b": "revenue"}, SCHEMA)
    assert errors


def test_missing_required_field_is_only_a_warning():
    errors, warnings = validate_mapping({"SALES": "revenue"}, SCHEMA)
    assert errors == []
    assert any("Product" in w for w in warnings)


def test_empty_mapping_is_an_error():
    errors, _ = validate_mapping({}, SCHEMA)
    assert errors


def test_curated_and_empty_names_are_never_learned():
    assert is_learnable("PRODUCTCODE") is None      # curated synonym of product_code
    assert is_learnable("!!!") is None              # normalizes to nothing
    assert is_learnable("Recette encaissée") == "recette encaissee"
