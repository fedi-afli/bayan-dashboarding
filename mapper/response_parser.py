import json
import re
def parse_response(response, schema=None):
    import json, re

    cleaned = response.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    if not cleaned.startswith("{"):
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise Exception(f"LLM did not return valid JSON. Raw output:\n{response}")
        cleaned = match.group(0)

    try:
        mapping = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise Exception(f"LLM did not return valid JSON: {e}\nRaw output:\n{response}")

    if schema:
        allowed = {f.lower(): f for f in schema["fields"].keys()}
        normalized = {}
        for src, tgt in mapping.items():
            if not tgt:
                normalized[src] = None
                continue
            match_field = allowed.get(tgt.strip().lower())
            normalized[src] = match_field  # None if no case-insensitive match either
        return normalized

    return mapping