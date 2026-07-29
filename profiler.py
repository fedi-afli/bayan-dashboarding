import argparse
import json
import sys
from dataclasses import dataclass
import pandas as pd


@dataclass
class ProfileOptions:
    file: str
    example_values: int = 3


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


def profile_csv(options: ProfileOptions):
    try:
        df = pd.read_csv(options.file)
    except FileNotFoundError:
        print(f"Error: File not found at '{options.file}'", file=sys.stderr)
        sys.exit(1)
    except pd.errors.EmptyDataError:
        print(f"Error: The file '{options.file}' is empty.", file=sys.stderr)
        sys.exit(1)
    except pd.errors.ParserError:
        print(
            f"Error: Failed to parse '{options.file}'. Make sure it's a valid CSV.",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error reading CSV file: {e}", file=sys.stderr)
        sys.exit(1)

    profile = {
        "columns": [],
    }

    for column in df.columns:
        profile["columns"].append(
            get_column_info(df[column], options.example_values)
        )

    return profile


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Profile a CSV file and output column metadata as JSON."
    )
    parser.add_argument(
        "file",
        type=str,
        help="Path to the CSV file",
    )
    parser.add_argument(
        "-e",
        "--example-values",
        type=int,
        default=3,
        help="Number of example values per column (default: 3)",
    )

    args = parser.parse_args()

    options = ProfileOptions(
        file=args.file,
        example_values=args.example_values,
    )

    try:
        profile = profile_csv(options)
        print(json.dumps(profile, indent=2, ensure_ascii=False))
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)