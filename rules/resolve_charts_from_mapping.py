"""
Chart rule engine.

Each ChartRule declares which schema fields must be present (and/or which
group of alternative fields at least one of must be present) for a chart
to make sense. `resolve_charts` matches the rules against whatever set of
target field names came out of the mapping step and returns a renderer-
agnostic list of chart configs.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ChartRule:
    name: str
    title: str
    chart_type: str  # "line", "bar", "pie", "scatter", "kpi"
    build: Callable[[set], dict]
    requires_all: set = field(default_factory=set)
    requires_any: set = field(default_factory=set)  # at least one of these must be present

    def matches(self, present_fields: set) -> bool:
        if not self.requires_all.issubset(present_fields):
            return False
        if self.requires_any and not (self.requires_any & present_fields):
            return False
        return True


def first_present(present_fields: set, candidates: list[str]) -> Optional[str]:
    """Return the first candidate (in priority order) that's present."""
    for c in candidates:
        if c in present_fields:
            return c
    return None


DATE_PRIORITY = ["sale_date", "order_date", "delivery_date"]
GEO_PRIORITY = ["city", "state", "territory", "country", "region_manager"]
TIME_BUCKET_PRIORITY = ["sale_month", "sale_quarter", "sale_year"]


CHART_RULES: list[ChartRule] = [
    ChartRule(
        name="revenue_over_time",
        title="Revenue Over Time",
        chart_type="line",
        requires_all={"revenue"},
        requires_any=set(DATE_PRIORITY),
        build=lambda fields: {
            "x": first_present(fields, DATE_PRIORITY),
            "y": "revenue",
            "agg": "sum",
        },
    ),
    ChartRule(
        name="quantity_over_time",
        title="Units Sold Over Time",
        chart_type="line",
        requires_all={"quantity"},
        requires_any=set(DATE_PRIORITY),
        build=lambda fields: {
            "x": first_present(fields, DATE_PRIORITY),
            "y": "quantity",
            "agg": "sum",
        },
    ),
    ChartRule(
        name="revenue_by_category",
        title="Revenue by Category",
        chart_type="bar",
        requires_all={"revenue", "category"},
        build=lambda fields: {"x": "category", "y": "revenue", "agg": "sum"},
    ),
    ChartRule(
        name="revenue_by_location",
        title="Revenue by Location",
        chart_type="bar",
        requires_all={"revenue"},
        requires_any=set(GEO_PRIORITY),
        build=lambda fields: {
            "x": first_present(fields, GEO_PRIORITY),
            "y": "revenue",
            "agg": "sum",
        },
    ),
    ChartRule(
        name="revenue_by_salesperson",
        title="Revenue by Salesperson",
        chart_type="bar",
        requires_all={"revenue", "salesperson"},
        build=lambda fields: {"x": "salesperson", "y": "revenue", "agg": "sum"},
    ),
    ChartRule(
        name="revenue_by_customer_type",
        title="Revenue by Customer Type",
        chart_type="pie",
        requires_all={"revenue", "customer_type"},
        build=lambda fields: {"group_by": "customer_type", "y": "revenue", "agg": "sum"},
    ),
    ChartRule(
        name="revenue_by_payment_method",
        title="Revenue by Payment Method",
        chart_type="pie",
        requires_all={"revenue", "payment_method"},
        build=lambda fields: {"group_by": "payment_method", "y": "revenue", "agg": "sum"},
    ),
    ChartRule(
        name="top_products_by_revenue",
        title="Top Products by Revenue",
        chart_type="bar",
        requires_all={"revenue", "product_name"},
        build=lambda fields: {
            "x": "product_name", "y": "revenue", "agg": "sum",
            "sort": "desc", "limit": 10,
        },
    ),
    ChartRule(
        name="revenue_vs_msrp",
        title="Revenue vs MSRP",
        chart_type="scatter",
        requires_all={"revenue", "msrp"},
        build=lambda fields: {"x": "msrp", "y": "revenue"},
    ),
    ChartRule(
        name="shipping_cost_vs_revenue",
        title="Shipping Cost vs Revenue",
        chart_type="scatter",
        requires_all={"revenue", "shipping_cost"},
        build=lambda fields: {"x": "shipping_cost", "y": "revenue"},
    ),
    ChartRule(
        name="discount_by_category",
        title="Average Discount by Category",
        chart_type="bar",
        requires_all={"discount", "category"},
        build=lambda fields: {"x": "category", "y": "discount", "agg": "avg"},
    ),
    ChartRule(
        name="order_status_breakdown",
        title="Order Status Breakdown",
        chart_type="pie",
        requires_all={"order_status"},
        build=lambda fields: {"group_by": "order_status", "agg": "count"},
    ),
    ChartRule(
        name="deal_size_distribution",
        title="Deal Size Distribution",
        chart_type="pie",
        requires_all={"deal_size"},
        build=lambda fields: {"group_by": "deal_size", "agg": "count"},
    ),
    ChartRule(
        name="return_rate",
        title="Return Rate",
        chart_type="kpi",
        requires_any={"returned", "nbr_returned"},
        build=lambda fields: {
            "measure": first_present(fields, ["nbr_returned", "returned"]),
            "agg": "sum" if "nbr_returned" in fields else "mean",
        },
    ),
    ChartRule(
        name="sales_by_time_bucket",
        title="Sales by Period",
        chart_type="bar",
        requires_all={"revenue"},
        requires_any=set(TIME_BUCKET_PRIORITY),
        build=lambda fields: {
            "x": first_present(fields, TIME_BUCKET_PRIORITY),
            "y": "revenue",
            "agg": "sum",
        },
    ),
    ChartRule(
        name="total_revenue_kpi",
        title="Total Revenue",
        chart_type="kpi",
        requires_all={"revenue"},
        build=lambda fields: {"measure": "revenue", "agg": "sum"},
    ),
    ChartRule(
        name="average_order_value_kpi",
        title="Average Order Value",
        chart_type="kpi",
        requires_all={"revenue", "quantity"},
        build=lambda fields: {"measure": "revenue", "agg": "sum_over_count", "divisor": "quantity"},
    ),
]


def resolve_charts(present_fields: set) -> list[dict]:
    """
    Match CHART_RULES against the set of schema field names present in the
    dataset and return the chart configs that apply.
    """
    charts = []
    for rule in CHART_RULES:
        if rule.matches(present_fields):
            charts.append({
                "name": rule.name,
                "title": rule.title,
                "chart_type": rule.chart_type,
                "config": rule.build(present_fields),
            })
    return charts


def resolve_charts_from_mapping(mapping: dict) -> list[dict]:
    """
    Convenience wrapper: takes the {raw_column: schema_field} mapping
    produced by BayanMapper and resolves the applicable charts directly.
    """
    present_fields = set(mapping.values())
    return resolve_charts(present_fields)