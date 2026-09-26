from engine.rules import resolve_charts


def names(charts):
    return {c["name"] for c in charts}


def test_average_order_value_is_a_real_ratio():
    charts = resolve_charts({"revenue", "invoice_number", "quantity"})
    aov = next(c for c in charts if c["name"] == "average_order_value")
    m = aov["config"]["metric"]
    assert m["agg"] == "ratio"
    assert m["num"] == {"agg": "sum", "field": "revenue"}
    assert m["den"] == {"agg": "count_distinct", "field": "invoice_number"}


def test_units_fallback_when_no_revenue():
    charts = resolve_charts({"quantity", "product_name", "sale_date"})
    trend = next(c for c in charts if c["name"] == "trend")
    assert trend["config"]["metric"] == {"agg": "sum", "field": "quantity"}
    assert "total_revenue" not in names(charts)


def test_single_value_dimensions_are_skipped():
    stats = {"country": {"distinct": 1, "null_ratio": 0.0},
             "city": {"distinct": 8, "null_ratio": 0.0}}
    charts = resolve_charts({"revenue", "country", "city"}, stats)
    loc = next(c for c in charts if c["name"] == "by_location")
    assert loc["config"]["dimension"] == "city"


def test_mostly_blank_dimension_is_skipped():
    stats = {"state": {"distinct": 10, "null_ratio": 0.7}, "city": {"distinct": 50, "null_ratio": 0.0}}
    charts = resolve_charts({"revenue", "state", "city"}, stats)
    assert next(c for c in charts if c["name"] == "by_location")["config"]["dimension"] == "city"


def test_analyst_charts_hidden_by_default():
    charts = resolve_charts({"revenue", "msrp", "quantity", "unit_price"})
    scatters = [c for c in charts if c["chart_type"] == "scatter"]
    assert scatters and not any(c["default_visible"] for c in scatters)
