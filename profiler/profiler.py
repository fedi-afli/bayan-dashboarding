import argparse
import json
from pathlib import Path
import sys
from dataclasses import dataclass
import pandas as pd


@dataclass
class ProfileOptions:
    file: str
    example_values: int = 3


def load_dataframe(file_path: str) -> pd.DataFrame:
    path = Path(file_path)

    if not path.exists():
        print(f"Error: File not found at '{file_path}'", file=sys.stderr)
        sys.exit(1)

    ext = path.suffix.lower()

    try:
        if ext in [".csv", ".txt"]:
            return pd.read_csv(file_path)
        elif ext in [".xlsx", ".xls", ".xlsm"]:
            return pd.read_excel(file_path)
        elif ext == ".parquet":
            return pd.read_parquet(file_path)
        elif ext == ".json":
            return pd.read_json(file_path)
        elif ext in [".feather", ".ftr"]:
            return pd.read_feather(file_path)
        elif ext in [".tsv"]:
            return pd.read_csv(file_path, sep="\t")
        else:
            print(
                f"Unsupported file format '{ext}'. Attempting default CSV reader...",
                file=sys.stderr,
            )
            return pd.read_csv(file_path)

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