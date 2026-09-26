import argparse
import json
from pathlib import Path
import sys
from dataclasses import dataclass
import pandas as pd

from charset_normalizer import from_path


class FileLoadError(ValueError):
    """The uploaded file couldn't be read into a table."""


@dataclass
class ProfileOptions:
    file: str
    example_values: int = 3


def detect_encoding(file_path: str, sample_size: int = 100_000) -> str:
    """
    Sniff the file's encoding instead of assuming UTF-8.
    Uses charset_normalizer to inspect the raw bytes and guess the most
    likely encoding. Falls back to latin-1 (which can decode ANY byte
    sequence, so it never raises) if detection is inconclusive.
    """
    result = from_path(file_path).best()

    if result is None or result.encoding is None:
        return "latin-1"

    return result.encoding


def read_csv_auto(file_path: str, **kwargs) -> pd.DataFrame:
    """
    Try strict UTF-8 first (fast path for the common case). If the file
    genuinely isn't UTF-8, detect the real encoding instead of guessing,
    and only fall back to lossy 'replace' as an absolute last resort so
    we never crash on a bad byte.
    """
    try:
        return pd.read_csv(file_path, encoding="utf-8", **kwargs)
    except UnicodeDecodeError:
        pass

    encoding = detect_encoding(file_path)

    try:
        return pd.read_csv(file_path, encoding=encoding, **kwargs)
    except UnicodeDecodeError:
        # last resort: never crash, just replace undecodable bytes
        return pd.read_csv(
            file_path,
            encoding=encoding,
            encoding_errors="replace",
            **kwargs,
        )


def load_dataframe(file_path: str) -> pd.DataFrame:
    path = Path(file_path)

    if not path.exists():
        raise FileLoadError(f"File not found: '{path.name}'")

    ext = path.suffix.lower()

    try:
        if ext in [".csv", ".txt"]:
            return read_csv_auto(file_path)
        elif ext == ".tsv":
            return read_csv_auto(file_path, sep="\t")
        elif ext in [".xlsx", ".xls", ".xlsm"]:
            return pd.read_excel(file_path)
        elif ext == ".parquet":
            return pd.read_parquet(file_path)
        elif ext == ".json":
            return pd.read_json(file_path)
        elif ext in [".feather", ".ftr"]:
            return pd.read_feather(file_path)
        else:
            print(
                f"Unsupported file format '{ext}'. Attempting default CSV reader...",
                file=sys.stderr,
            )
            return read_csv_auto(file_path)

    except pd.errors.EmptyDataError:
        raise FileLoadError(f"The file '{path.name}' is empty.")
    except pd.errors.ParserError:
        raise FileLoadError(f"Couldn't parse '{path.name}' — is it really a {ext or 'CSV'} file?")
    except ImportError as e:
        raise FileLoadError(f"Missing library to read '{ext}' files ({e}).")
    except Exception as e:
        raise FileLoadError(f"Couldn't read '{path.name}': {e}")


def get_column_info(series: pd.Series, example_count: int):
    values = series.dropna()

    if values.empty:
        return {
            "name": series.name,
            "type": "empty",
            "examples": [],
        }

    info = {"name": series.name}

    if pd.api.types.is_integer_dtype(series):
        info["type"] = "integer"
        info["examples"] = values.head(example_count).tolist()
        info["min"] = int(values.min())
        info["max"] = int(values.max())

    elif pd.api.types.is_float_dtype(series):
        info["type"] = "float"
        info["examples"] = values.head(example_count).tolist()
        info["min"] = float(values.min())
        info["max"] = float(values.max())

    elif pd.api.types.is_bool_dtype(series):
        info["type"] = "boolean"
        info["examples"] = values.unique().tolist()[:example_count]

    elif pd.api.types.is_datetime64_any_dtype(series):
        info["type"] = "datetime"
        info["examples"] = values.astype(str).head(example_count).tolist()

    else:
        info["type"] = "string"
        info["examples"] = (
            values.astype(str).drop_duplicates().head(example_count).tolist()
        )
        info["unique_count"] = int(values.nunique())

    info["avg_bytes"] = _avg_stored_bytes(values, info["type"])
    return info


def _avg_stored_bytes(values: pd.Series, col_type: str) -> float:
    """Average size of one value once stored in Postgres (used to estimate storage before loading)."""
    if col_type in ("integer", "float", "datetime"):
        return 8.0
    if col_type == "boolean":
        return 1.0
    sample = values.sample(50_000, random_state=0) if len(values) > 50_000 else values
    # UTF-8 length + 1-byte varlena header for short strings
    return round(float(sample.astype(str).str.encode("utf-8").str.len().mean()) + 1, 1)


def profile_file(options: ProfileOptions) -> tuple[pd.DataFrame, dict]:
    """Returns (dataframe, profile)."""
    df = load_dataframe(options.file)

    # drop fully blank columns/rows (spreadsheet padding), stringify headers
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    if df.empty or len(df.columns) == 0:
        raise FileLoadError("The file has no data rows.")
    if len(set(df.columns)) != len(df.columns):
        dupes = sorted({c for c in df.columns if list(df.columns).count(c) > 1})
        raise FileLoadError(f"Some column names appear twice: {dupes}. Rename them and upload again.")

    profile = {
        "columns": [],
    }

    for column in df.columns:
        profile["columns"].append(
            get_column_info(df[column], options.example_values)
        )

    return df, profile