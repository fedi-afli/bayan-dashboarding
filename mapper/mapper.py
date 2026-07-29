from .schema_loader import load_schema
from .prompt_builder import build_mapping_prompt
from .llm_client import HuggingFaceClient
from .validator import validate_mapping
from matchers.hybrid_matcher import HybridMatcher
from matchers.plausibility import check_llm_mapping_plausibility
from matchers.synonym_store import confirm_synonym


class BayanMapper:
    def __init__(self):
        self.schema = load_schema()
        self.matcher = HybridMatcher(self.schema)
        self.llm = HuggingFaceClient()

    def map(self, profile):
        columns = profile["columns"]
        mapping = {}
        confidences = {}
        methods = {}
        unresolved = []

        # Step 1: deterministic matching (synonyms -> fuzzy -> embeddings)
        for col in columns:
            field, confidence, method = self.matcher.match_column(col["name"])
            if field is not None:
                mapping[col["name"]] = field
                confidences[col["name"]] = confidence
                methods[col["name"]] = method
            else:
                unresolved.append(col)

        unresolved += self._resolve_duplicates(mapping, confidences, columns)

        review_notes = []
        needs_confirmation = []  # [{ "source": ..., "suggested_field": ..., "reason": ... }]

        if unresolved:
            remaining_fields = [f for f in self.schema["fields"] if f not in mapping.values()]
            if remaining_fields:
                fallback, suspicious = self._llm_fallback(unresolved, remaining_fields)

                mapping.update(fallback)
                for src in fallback:
                    methods[src] = "llm"

                resolved_names = set(fallback)
                unresolved = [c for c in unresolved if c["name"] not in resolved_names]

                if suspicious:
                    review_notes.append(
                        f"{len(suspicious)} LLM mapping(s) worth a manual glance "
                        f"(no literal name overlap with target field — may still be correct): {suspicious}"
                    )
                    for src, tgt in suspicious.items():
                        needs_confirmation.append({
                            "source": src,
                            "suggested_field": tgt,
                            "reason": "no_name_overlap",
                        })

                dupes = self._resolve_duplicates(mapping, confidences, columns)
                if dupes:
                    review_notes.append(
                        f"{len(dupes)} column(s) still ambiguous after LLM fallback"
                    )
                    unresolved += dupes

        # Colonnes jamais résolues -> le client doit choisir manuellement,
        # pas seulement confirmer une suggestion
        for col in unresolved:
            needs_confirmation.append({
                "source": col["name"],
                "suggested_field": None,
                "reason": "unresolved",
            })

        errors, warnings = validate_mapping(mapping, self.schema, profile)

        status = "ok"
        if errors:
            status = "error"
        elif warnings or unresolved or needs_confirmation:
            status = "needs_review"

        return {
            "mapping": mapping,
            "status": status,
            "unresolved_columns": [c["name"] for c in unresolved],
            "needs_confirmation": needs_confirmation,
            "errors": errors,
            "warnings": warnings,
            "notes": review_notes,
        }

    def confirm_field(self, source_column: str, target_field: str):
        """
        Appelé quand le client confirme (ou corrige) un mapping incertain
        pour une colonne donnée. Enregistre dans learned_synonyms.json et
        recharge le matcher pour que la colonne soit reconnue directement
        la prochaine fois, sans passer par le LLM.
        """
        confirm_synonym(source_column, target_field)
        self.matcher.reload_synonyms()

    def _resolve_duplicates(self, mapping, confidences, columns):
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
                    bumped.append(next(c for c in columns if c["name"] == loser))

        return bumped

    def _llm_fallback(self, columns, remaining_fields):
        sub_schema = {"fields": {f: self.schema["fields"][f] for f in remaining_fields}}
        sub_profile = {"columns": columns}

        prompt = build_mapping_prompt(sub_schema, sub_profile)
        column_names = [c["name"] for c in columns]

        raw_mapping = self.llm.generate_mapping(
            prompt=prompt,
            column_names=column_names,
            allowed_fields=remaining_fields,
        )

        candidate = {k: v for k, v in raw_mapping.items() if v}
        suspicious = check_llm_mapping_plausibility(candidate, self.schema)

        return candidate, suspicious