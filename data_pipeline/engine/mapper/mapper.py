import time

from .schema_loader import load_schema
from .prompt_builder import build_mapping_prompt
from .validator import validate_mapping
from ..matchers.hybrid_matcher import HybridMatcher
from ..matchers.type_compat import compatible_fields, is_compatible


class BayanMapper:
    def __init__(self, load_llm: bool = True):
        self.schema = load_schema()
        self.matcher = HybridMatcher(self.schema)
        self.llm = None
        if load_llm:
            # imported lazily: pulls in torch/transformers/outlines
            from .llm_client import HuggingFaceClient
            self.llm = HuggingFaceClient()

    def _field_type(self, field):
        return self.schema["fields"][field]["type"]

    def map(self, profile, learned=None):
        """
        learned: this account's confirmed synonyms {field: {normalized names}}.
        """
        columns = [c for c in profile["columns"] if c["type"] != "empty"]
        ai = {"columns": 0, "seconds": 0.0}  # AI work done for this file (metered for pricing)
        mapping = {}
        confidences = {}
        methods = {}
        unresolved = []
        notes = []

        # Step 1: deterministic matching (synonyms -> fuzzy -> embeddings),
        # rejecting anything whose type can't hold this column's values
        for col in columns:
            field, confidence, method = self.matcher.match_column(col["name"], learned)
            if field is not None and not is_compatible(col["type"], self._field_type(field)):
                notes.append(
                    f"'{col['name']}' looks like '{field}' by name, but its values "
                    f"({col['type']}) don't fit that field — left for you to decide"
                )
                field = None
            if field is not None:
                mapping[col["name"]] = field
                confidences[col["name"]] = confidence
                methods[col["name"]] = method
            else:
                unresolved.append(col)

        unresolved += self._resolve_duplicates(mapping, confidences, methods, columns)

        # Step 2: LLM fallback, each column restricted to type-compatible fields
        if unresolved and self.llm is not None:
            remaining = [f for f in self.schema["fields"] if f not in mapping.values()]
            allowed = {
                c["name"]: compatible_fields(c["type"], self.schema, remaining) for c in unresolved
            }
            allowed = {k: v for k, v in allowed.items() if v}
            if allowed:
                started = time.perf_counter()
                fallback = self._llm_fallback(
                    [c for c in unresolved if c["name"] in allowed], remaining, allowed
                )
                ai = {"columns": len(allowed), "seconds": round(time.perf_counter() - started, 3)}
                for src, tgt in fallback.items():
                    mapping[src] = tgt
                    methods[src] = "llm"
                    confidences[src] = 0.5
                unresolved = [c for c in unresolved if c["name"] not in fallback]
                unresolved += self._resolve_duplicates(mapping, confidences, methods, columns)

        unresolved_names = {c["name"] for c in unresolved}
        needs_confirmation = []
        column_details = []
        for col in profile["columns"]:
            name = col["name"]
            method = methods.get(name)
            if col["type"] == "empty":
                reason = "empty"
            elif name in unresolved_names:
                reason = "unresolved"
            elif method == "llm":
                reason = "ai_guess"
            elif method == "embedding":
                reason = "low_confidence"
            else:
                reason = None

            if reason in ("unresolved", "ai_guess", "low_confidence"):
                needs_confirmation.append({
                    "source": name,
                    "suggested_field": mapping.get(name),
                    "reason": reason,
                })

            column_details.append({
                "name": name,
                "type": col["type"],
                "examples": col.get("examples", []),
                "target": mapping.get(name),
                "method": method,
                "confidence": round(float(confidences.get(name, 0.0)), 2),
                "review_reason": reason,
            })

        errors, warnings = validate_mapping(mapping, self.schema, profile)

        status = "ok"
        if errors:
            status = "error"
        elif warnings or needs_confirmation:
            status = "needs_review"

        return {
            "mapping": mapping,
            "columns": column_details,
            "status": status,
            "unresolved_columns": [c["name"] for c in unresolved],
            "needs_confirmation": needs_confirmation,
            "errors": errors,
            "warnings": warnings,
            "notes": notes,
            "ai": ai,
        }

    def _resolve_duplicates(self, mapping, confidences, methods, columns):
        target_to_sources = {}
        for src, tgt in mapping.items():
            if tgt:
                target_to_sources.setdefault(tgt, []).append(src)

        bumped = []
        for tgt, sources in target_to_sources.items():
            if len(sources) > 1:
                sources.sort(key=lambda s: confidences.get(s, 0), reverse=True)
                for loser in sources[1:]:
                    del mapping[loser]
                    confidences.pop(loser, None)
                    methods.pop(loser, None)
                    bumped.append(next(c for c in columns if c["name"] == loser))

        return bumped

    def _llm_fallback(self, columns, remaining_fields, allowed_by_column):
        sub_schema = {"fields": {f: self.schema["fields"][f] for f in remaining_fields}}
        prompt = build_mapping_prompt(sub_schema, {"columns": columns})
        raw_mapping = self.llm.generate_mapping(prompt=prompt, allowed_by_column=allowed_by_column)
        return {
            k: v for k, v in raw_mapping.items()
            if v and v in allowed_by_column.get(k, [])
        }
