"""Engine storage + chart queries, against the migrated test database."""
import uuid
from datetime import date

import pandas as pd
import pytest

from engine import storage
from engine.derived_fields import column_stats
from engine.queries import DateFilter, QueryContext, check_chart, run_chart_query
from engine.rules import resolve_charts

TENANT = "tenant-a"


@pytest.fixture
def dataset(migrated_db):
    ds_id = f"test-{uuid.uuid4()}"
    df = pd.DataFrame({
        "invoice_number": ["A", "A", "B", "C", "D"],
        "product_name": ["Chaise", "Table", "Chaise", "Lampe", "Tapis"],
        "quantity": [1, 2, 3, 1, 1],
        "revenue": [10.0, 40.0, 30.0, 5.0, 15.0],
        # dates arrive as text, US style, like the Kaggle sample
        "sale_date": ["1/5/2024 0:00", "1/5/2024 0:00", "2/10/2024 0:00", "3/1/2024 0:00", "not a date"],
        "returned": [0, 1, 0, 0, 0],
    })
    storage.create_pending(TENANT, ds_id, "t.csv", "/nonexistent", len(df), {"columns": []}, {"columns": []})
    types = storage.column_types_for(df)
    charts = resolve_charts(set(df.columns), column_stats(df))
    storage.save_dataset(TENANT, ds_id, df, types, {}, charts, [])
    yield ds_id, df, types, {c["name"]: c for c in charts}
    storage.delete_dataset(TENANT, ds_id)


def run(ds, name, **filters):
    ds_id, _, types, charts = ds
    ctx = QueryContext(storage.table_name_for(ds_id), types,
                       DateFilter("sale_date", filters.get("date_from"), filters.get("date_to")))
    return run_chart_query(charts[name], ctx)


def test_kpis(dataset):
    assert run(dataset, "total_revenue")["value"] == 100.0
    assert run(dataset, "orders")["value"] == 4
    assert run(dataset, "average_order_value")["value"] == pytest.approx(25.0)   # 100 / 4 orders
    assert run(dataset, "return_rate")["value"] == pytest.approx(0.2)


def test_saving_again_replaces_instead_of_appending(dataset):
    ds_id, df, types, charts = dataset
    storage.save_dataset(TENANT, ds_id, df, types, {}, list(charts.values()), [])
    assert run(dataset, "total_revenue")["value"] == 100.0


def test_text_dates_are_bucketed_and_bad_values_ignored(dataset):
    data = run(dataset, "trend")
    rows = data["rows"]
    assert data["granularity"] == "day"          # 56-day span
    assert [r["label"] for r in rows] == ["2024-01-05", "2024-02-10", "2024-03-01"]
    assert sum(r["value"] for r in rows) == 85.0     # the "not a date" row is excluded


def test_date_filter_applies_to_kpis(dataset):
    v = run(dataset, "total_revenue", date_from=date(2024, 2, 1), date_to=date(2024, 2, 29))
    assert v["value"] == 30.0


def test_breakdown_top_n_and_other(dataset):
    ds_id, _, types, charts = dataset
    spec = dict(charts["top_products"])
    spec["config"] = dict(spec["config"], top=2)
    data = run_chart_query(spec, QueryContext(storage.table_name_for(ds_id), types))
    labels = [r["label"] for r in data["rows"]]
    assert labels[:2] == ["Chaise", "Table"]
    assert data["rows"][-1] == {"label": "Other", "value": 20.0, "is_other": True}


def test_text_column_is_not_offered_as_a_measure(dataset):
    _, _, types, charts = dataset
    bad = dict(charts["total_revenue"], config={"metric": {"agg": "sum", "field": "product_name"}})
    with pytest.raises(Exception):
        check_chart(bad, QueryContext("x", types))


def test_other_tenants_cannot_see_or_overwrite_a_dataset(dataset):
    ds_id, df, types, charts = dataset
    assert storage.get_dataset("tenant-b", ds_id) is None
    assert all(d["id"] != ds_id for d in storage.list_datasets("tenant-b"))
    with pytest.raises(LookupError):
        storage.save_dataset("tenant-b", ds_id, df, types, {}, [], [])
    assert storage.delete_dataset("tenant-b", ds_id) is False
    assert storage.get_dataset(TENANT, ds_id) is not None


def test_learned_synonyms_are_per_tenant(migrated_db):
    storage.learn_synonym("tenant-a", "recette", "revenue")
    storage.learn_synonym("tenant-a", "recette", "quantity")   # first confirmation wins
    assert storage.load_learned_synonyms("tenant-a")["revenue"] == {"recette"}
    assert "recette" not in storage.load_learned_synonyms("tenant-b").get("revenue", set())
