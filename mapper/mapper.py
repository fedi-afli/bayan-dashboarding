from .schema_loader import load_schema
from .prompt_builder import build_mapping_prompt
from .llm_client import HuggingFaceClient
from .response_parser import parse_response
from .validator import validate_mapping
from matchers.hybrid_matcher import HybridMatcher


class BayanMapper:
    def __init__(self):
        self.schema = load_schema()
        self.matcher = HybridMatcher(self.schema)
        self.llm = HuggingFaceClient()

    def map(self, profile):
        columns = profile["columns"]
        mapping = {}
        confidences = {}
        unresolved = []

        # Step 1: deterministic matching (fuzzy + embeddings)
        for col in columns:
            field, confidence, method = self.matcher.match_column(col["name"])
            if field is not None:
                mapping[col["name"]] = field
                confidences[col["name"]] = confidence
            else:
                unresolved.append(col)

        # Step 2: resolve duplicate targets — keep the higher-confidence column,
        # send the loser back to the LLM instead of silently dropping it
        target_to_sources = {}
        for src, tgt in mapping.items():
            target_to_sources.setdefault(tgt, []).append(src)

        for tgt, sources in target_to_sources.items():
            if len(sources) > 1:
                sources.sort(key=lambda s: confidences[s], reverse=True)
                for loser in sources[1:]:
                    del mapping[loser]
                    unresolved.append(next(c for c in columns if c["name"] == loser))

        # Step 3: LLM fallback for whatever's still unresolved
        if unresolved:
            remaining_fields = [f for f in self.schema["fields"] if f not in mapping.values()]
            if remaining_fields:
                fallback = self._llm_fallback(unresolved, remaining_fields)
                mapping.update(fallback)

        validate_mapping(mapping, self.schema, profile)
        return mapping

    def _llm_fallback(self, columns, remaining_fields):
        sub_schema = {"fields": {f: self.schema["fields"][f] for f in remaining_fields}}
        sub_profile = {"columns": columns}

        prompt = build_mapping_prompt(sub_schema, sub_profile)
        response = self.llm.generate(prompt)
        raw_mapping = parse_response(response, sub_schema)

        # guard against the model hallucinating columns that were never in this batch
        real_names = {c["name"] for c in columns}
        return {k: v for k, v in raw_mapping.items() if k in real_names and v}