import argparse
import json
from pathlib import Path
import sys
from dataclasses import dataclass
import pandas as pd

from charset_normalizer import from_path


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
        print(f"Error: File not found at '{file_path}'", file=sys.stderr)
        sys.exit(1)

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
        print(f"Error: The file '{file_path}' is empty.", file=sys.stderr)
        sys.exit(1)
    except pd.errors.ParserError:
        print(
            f"Error: Failed to parse '{file_path}'. Ensure the format matches the extension.",
            file=sys.stderr,
        )
        sys.exit(1)
    except ImportError as e:
        print(
            f"Error: Missing engine library to read '{ext}' files. ({e})",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}", file=sys.stderr)
        sys.exit(1)


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

    return info


def profile_file(options: ProfileOptions):
    df = load_dataframe(options.file)

    profile = {
        "columns": [],
    }

    for column in df.columns:
        profile["columns"].append(
            get_column_info(df[column], options.example_values)
        )

    return profile