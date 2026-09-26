"""
Chart rule engine.

Given the set of schema fields that made it into a dataset (and, when
available, simple per-field stats from the loaded data), decide which
charts make sense and how they should be computed. Output is
renderer-agnostic: a list of chart specs

    {name, title, chart_type, size, default_visible, config}

chart_type: "kpi" | "line" | "bar" | "donut" | "scatter"
config.metric: {"agg": "sum"|"avg"|"count"|"count_distinct"|"rate", "field": ...}
            or {"agg": "ratio", "num": <metric>, "den": <metric>}
config.format: "currency" | "number" | "percent"

The dashboard shows `default_visible` charts up front and keeps the rest
one click away, so the first screen stays readable.
"""

from typing import Optional

DATE_PRIORITY = ["sale_date", "order_date", "delivery_date"]
GEO_PRIORITY = ["state", "city", "country", "territory"]

# a breakdown with fewer distinct values than this is pointless
MIN_GROUPS = 2
# donuts stop being readable past this many slices (we still group into "Other")
MAX_DONUT_GROUPS = 12


def first_present(present_fields: set, candidates: list[str]) -> Optional[str]:
    """Return the first candidate (in priority order) that's present."""
    for c in candidates:
        if c in present_fields:
            return c
    return None


def _useful_dimension(field: str, stats: Optional[dict], max_groups: Optional[int] = None) -> bool:
    """A grouping field is useful if it splits the data into >1 group and is mostly filled."""
    if stats is None or field not in stats:
        return True
    s = stats[field]
    if s["distinct"] < MIN_GROUPS or s["null_ratio"] > 0.5:
        return False
    if max_groups is not None and s["distinct"] > max_groups * 4:
        return False
    return True


def main_metric(fields: set) -> tuple[dict, str, str]:
    """The dataset's main "how much" measure: revenue, else units, else row count."""
    if "revenue" in fields:
        return {"agg": "sum", "field": "revenue"}, "currency", "Revenue"
    if "quantity" in fields:
        return {"agg": "sum", "field": "quantity"}, "number", "Units sold"
    return {"agg": "count"}, "number", "Transactions"


def _chart(name, title, chart_type, config, visible=True, size=None):
    return {
        "name": name,
        "title": title,
        "chart_type": chart_type,
        "size": size or {"kpi": "kpi", "line": "wide"}.get(chart_type, "half"),
        "default_visible": visible,
        "config": config,
    }


def resolve_charts(present_fields: set, stats: Optional[dict] = None) -> list[dict]:
    f = set(present_fields)
    charts = []
    metric, fmt, metric_label = main_metric(f)
    date_field = first_present(f, DATE_PRIORITY)

    # ---------- KPIs ----------
    if "revenue" in f:
        charts.append(_chart("total_revenue", "Total revenue", "kpi",
                             {"metric": {"agg": "sum", "field": "revenue"}, "format": "currency"}))

    if "invoice_number" in f:
        charts.append(_chart("orders", "Orders", "kpi",
                             {"metric": {"agg": "count_distinct", "field": "invoice_number"}, "format": "number"}))
    else:
        charts.append(_chart("transactions", "Transactions", "kpi",
                             {"metric": {"agg": "count"}, "format": "number"}))

    if "quantity" in f:
        charts.append(_chart("units_sold", "Units sold", "kpi",
                             {"metric": {"agg": "sum", "field": "quantity"}, "format": "number"}))

    if "revenue" in f and "invoice_number" in f:
        charts.append(_chart("average_order_value", "Average order value", "kpi", {
            "metric": {"agg": "ratio",
                       "num": {"agg": "sum", "field": "revenue"},
                       "den": {"agg": "count_distinct", "field": "invoice_number"}},
            "format": "currency",
        }))
    elif "revenue" in f:
        charts.append(_chart("average_sale", "Average sale", "kpi",
                             {"metric": {"agg": "avg", "field": "revenue"}, "format": "currency"}))

    if "returned" in f:
        charts.append(_chart("return_rate", "Return rate", "kpi",
                             {"metric": {"agg": "rate", "field": "returned"}, "format": "percent"}))
    elif "nbr_returned" in f and "quantity" in f:
        charts.append(_chart("return_rate", "Return rate", "kpi", {
            "metric": {"agg": "ratio",
                       "num": {"agg": "sum", "field": "nbr_returned"},
                       "den": {"agg": "sum", "field": "quantity"}},
            "format": "percent",
        }))

    if "discount" in f:
        charts.append(_chart("average_discount", "Average discount", "kpi",
                             {"metric": {"agg": "avg", "field": "discount"}, "format": "number"},
                             visible=False))

    # ---------- trend ----------
    if date_field:
        charts.append(_chart("trend", f"{metric_label} over time", "line",
                             {"time": date_field, "metric": metric, "format": fmt}))
        if metric.get("field") == "revenue" and "quantity" in f:
            charts.append(_chart("units_trend", "Units sold over time", "line",
                                 {"time": date_field, "metric": {"agg": "sum", "field": "quantity"},
                                  "format": "number"}, visible=False))
    elif "sale_year" in f:
        period = ["sale_year"] + (["sale_month"] if "sale_month" in f else [])
        charts.append(_chart("trend", f"{metric_label} by period", "line",
                             {"period": period, "metric": metric, "format": fmt}))

    # ---------- breakdowns (top 10 + Other) ----------
    def breakdown(name, title, field, visible=True, chart_type="bar", top=10):
        max_groups = MAX_DONUT_GROUPS if chart_type == "donut" else None
        if field in f and _useful_dimension(field, stats, max_groups):
            charts.append(_chart(name, title, chart_type, {
                "dimension": field, "metric": metric, "format": fmt, "top": top,
            }, visible=visible))

    product_field = "product_name" if "product_name" in f else "product_code"
    breakdown("by_category", f"{metric_label} by category", "category")
    breakdown("top_products", f"Top products by {metric_label.lower()}", product_field)
    breakdown("top_customers", f"Top customers by {metric_label.lower()}", "customer_name")

    geo = next((g for g in GEO_PRIORITY if g in f and _useful_dimension(g, stats)), None)
    if geo:
        breakdown("by_location", f"{metric_label} by location", geo)

    breakdown("by_salesperson", f"{metric_label} by salesperson", "salesperson")
    breakdown("by_store", f"{metric_label} by store", "store_location", visible=False)

    breakdown("by_payment_method", "Payment methods", "payment_method", chart_type="donut", top=6)
    breakdown("by_customer_type", "Customer types", "customer_type", chart_type="donut", top=6)

    if "order_status" in f and _useful_dimension("order_status", stats, MAX_DONUT_GROUPS):
        charts.append(_chart("order_status", "Order status", "donut", {
            "dimension": "order_status", "metric": {"agg": "count"}, "format": "number", "top": 6,
        }))
    if "deal_size" in f and _useful_dimension("deal_size", stats, MAX_DONUT_GROUPS):
        charts.append(_chart("deal_size", "Deal sizes", "donut", {
            "dimension": "deal_size", "metric": {"agg": "count"}, "format": "number", "top": 6,
        }, visible=False))

    # ---------- secondary / analyst charts: available, hidden by default ----------
    if metric.get("field") == "revenue" and "quantity" in f and product_field in f:
        charts.append(_chart("top_products_units", "Top products by units sold", "bar", {
            "dimension": product_field, "metric": {"agg": "sum", "field": "quantity"},
            "format": "number", "top": 10,
        }, visible=False))

    if "discount" in f and "category" in f:
        charts.append(_chart("discount_by_category", "Average discount by category", "bar", {
            "dimension": "category", "metric": {"agg": "avg", "field": "discount"},
            "format": "number", "top": 10,
        }, visible=False))

    for x, y, title in [("msrp", "revenue", "Sales vs list price"),
                        ("shipping_cost", "revenue", "Sales vs shipping cost"),
                        ("unit_price", "quantity", "Unit price vs quantity")]:
        if x in f and y in f:
            charts.append(_chart(f"{x}_vs_{y}", title, "scatter", {"x": x, "y": y}, visible=False))

    return charts


def resolve_charts_from_mapping(mapping: dict, stats: Optional[dict] = None) -> list[dict]:
    """Convenience wrapper over the {raw_column: schema_field} mapping."""
    return resolve_charts(set(mapping.values()), stats)
