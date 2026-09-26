from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer, util
from .synonym_store import get_static_synonyms, normalize


class HybridMatcher:
    def __init__(self, schema, embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                 fuzzy_threshold=85, embedding_threshold=0.55):
        self.schema = schema
        self.fuzzy_threshold = fuzzy_threshold
        self.embedding_threshold = embedding_threshold
        self.model = SentenceTransformer(embedding_model)

        self.field_names = list(schema["fields"].keys())

        # curated synonyms only: learned ones are per account and passed to match_column()
        self.static_synonyms = get_static_synonyms()

        # each field gets its name + synonyms embedded together as a single reference text
        self.field_texts = {
            f: ", ".join([f.replace("_", " ")] + sorted(self.static_synonyms.get(f, [])))
            for f in self.field_names
        }
        self.field_embeddings = self.model.encode(
            list(self.field_texts.values()), convert_to_tensor=True
        )

    def match_column(self, column_name, learned=None):
        """
        Returns (best_field_or_None, confidence_0_to_1, method).
        learned: {field: {normalized synonyms}} confirmed by this account —
        checked after the curated synonyms, so it can never shadow them.
        """
        normalized = normalize(column_name)

        # Pass 1: exact match against confirmed/curated synonyms —
        # cheapest and highest-confidence signal, checked first
        if not normalized:
            return None, 0.0, "low_confidence"

        for pass_synonyms in (self.static_synonyms, learned or {}):
            for field, syns in pass_synonyms.items():
                if field in self.schema["fields"] and normalized in syns:
                    return field, 1.0, "synonym"

        # Pass 2: fuzzy string match against field name + each synonym individually
        best_fuzzy_field, best_fuzzy_score = None, 0
        for field, text in self.field_texts.items():
            for candidate in text.split(", "):
                score = fuzz.ratio(normalized, candidate)
                if score > best_fuzzy_score:
                    best_fuzzy_score, best_fuzzy_field = score, field

        if best_fuzzy_score >= self.fuzzy_threshold:
            return best_fuzzy_field, best_fuzzy_score / 100, "fuzzy"

        # Pass 3: semantic similarity for non-lexical matches
        col_embedding = self.model.encode(normalized, convert_to_tensor=True)
        sims = util.cos_sim(col_embedding, self.field_embeddings)[0]
        best_idx = int(sims.argmax())
        best_score = float(sims[best_idx])

        if best_score >= self.embedding_threshold:
            return self.field_names[best_idx], best_score, "embedding"

        return None, best_score, "low_confidence"