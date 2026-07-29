import json


def load_schema(path="schemas/sales_schema.json"):
    with open(path, "r") as file:
        return json.load(file)