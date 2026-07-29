import json
import sys

from profiler.profiler import ProfileOptions, profile_file
from mapper.mapper import BayanMapper


def run_pipeline(file_path: str):

    options = ProfileOptions(
        file=file_path,
        example_values=3
    )

    profile = profile_file(options)

    mapper = BayanMapper()

    mapping = mapper.map(profile)

    return profile, mapping


if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage:")
        print("python main.py data/raw/sales.csv")
        sys.exit(1)

    profile, mapping = run_pipeline(sys.argv[1])

    print("\n===== PROFILE =====")
    print(json.dumps(profile, indent=4, ensure_ascii=False))

    print("\n===== MAPPING =====")
    print(json.dumps(mapping, indent=4, ensure_ascii=False))