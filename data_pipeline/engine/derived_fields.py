"""
Turns the raw upload into the frame we store: keep mapped columns under
their schema names, then fill in commonly-needed fields that can be
computed from others, so chart rules aren't starved just because the
source file never had an explicit column for them.
"""

import pandas as pd


def apply_mapping(dataset: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """
    Keep only the mapped columns, renamed to their schema field names.
    Keys that aren't real columns (e.g. synthetic derived entries) are ignored.
    """
    mapped_columns = [col for col in dataset.columns if mapping.get(col)]
    if not mapped_columns:
        raise ValueError("No columns in the dataset match the mapping — nothing to load.")

    return dataset[mapped_columns].rename(columns=mapping)


def augment_mapping(mapping: dict) -> dict:
    """
    Add synthetic mapping entries for fields we can derive, so chart rules
    see them as present. Synthetic keys never match a real source column.
    """
    present = set(mapping.values())
    augmented = dict(mapping)

    if "revenue" not in present and {"quantity", "unit_price"}.issubset(present):
        augmented["__derived_revenue__"] = "revenue"

    return augmented


def compute_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute derived columns on the already-mapped frame (run AFTER apply_mapping).

    Revenue is GROSS (quantity * unit_price), and only computed when both
    columns really are numeric — text like "3,50 DT" is left alone rather
    than guessed at.
    """
    df = df.copy()
    if (
        "revenue" not in df.columns
        and {"quantity", "unit_price"}.issubset(df.columns)
        and pd.api.types.is_numeric_dtype(df["quantity"])
        and pd.api.types.is_numeric_dtype(df["unit_price"])
    ):
        df["revenue"] = df["quantity"] * df["unit_price"]
    return df


def column_stats(df: pd.DataFrame) -> dict:
    """{field: {"distinct": n, "null_ratio": r}} — lets chart rules skip useless breakdowns."""
    n = max(len(df), 1)
    return {
        col: {
            "distinct": int(df[col].nunique(dropna=True)),
            "null_ratio": float(df[col].isna().sum()) / n,
        }
        for col in df.columns
    }
