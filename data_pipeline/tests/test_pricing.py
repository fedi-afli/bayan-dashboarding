import pytest

from saas.pricing import Rates, examples, quote


def drivers(rows, cols, ai=0, bytes_per_cell=13):
    return {"rows": rows, "columns": cols, "cells": rows * cols,
            "storage_bytes": rows * cols * bytes_per_cell, "ai_columns": ai}


def test_small_files_cost_the_minimum():
    assert quote(drivers(7, 6))["credits"] == 1
    assert quote(drivers(2_823, 25))["credits"] == 1


def test_price_grows_with_the_data():
    prices = [quote(drivers(n, 10))["credits"] for n in (1_000, 50_000, 200_000, 500_000)]
    assert prices == sorted(prices) and prices[0] < prices[-1]
    assert quote(drivers(500_000, 10))["credits"] >= 7


def test_more_columns_cost_more():
    assert quote(drivers(200_000, 20))["credits"] > quote(drivers(200_000, 5))["credits"]


def test_ai_matching_is_charged_per_column():
    without = quote(drivers(100_000, 10))
    with_ai = quote(drivers(100_000, 10, ai=8))
    assert with_ai["exact"] - without["exact"] == pytest.approx(8 * Rates().per_ai_column)
    assert any(line["key"] == "ai" for line in with_ai["lines"])
    assert not any(line["key"] == "ai" for line in without["lines"])


def test_total_is_rounded_up_and_lines_add_up():
    q = quote(drivers(60_000, 10))
    assert q["credits"] >= q["exact"] > q["credits"] - 1
    assert abs(sum(line["amount"] for line in q["lines"]) - q["exact"]) < 0.05


def test_examples_are_ordered_by_size():
    credits = [e["credits"] for e in examples()]
    assert credits == sorted(credits)
