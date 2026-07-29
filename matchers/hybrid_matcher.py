from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer, util
from .synonyms import FIELD_SYNONYMS


class HybridMatcher:
    def __init__(self, schema, embedding_model="sentence-transformers/all-MiniLM-L6-v2",
                 fuzzy_threshold=85, embedding_threshold=0.55):
        self.schema = schema
        self.fuzzy_threshold = fuzzy_threshold
        self.embedding_threshold = embedding_threshold
        self.model = SentenceTransformer(embedding_model)

        self.field_names = list(schema["fields"].keys())
        # each field gets its name + synonyms embedded together as a single reference text
        self.field_texts = {
            f: ", ".join([f.replace("_", " ")] + FIELD_SYNONYMS.get(f, []))
            for f in self.field_names
        }
        self.field_embeddings = self.model.encode(
            list(self.field_texts.values()), convert_to_tensor=True
        )

    def match_column(self, column_name):
        """Returns (best_field_or_None, confidence_0_to_1, method)."""
        normalized = column_name.strip().lower()

        # Pass 1: fuzzy string match against field name + each synonym individually
        best_fuzzy_field, best_fuzzy_score = None, 0
        for field, text in self.field_texts.items():
            for candidate in text.split(", "):
                score = fuzz.ratio(normalized, candidate)
                if score > best_fuzzy_score:
                    best_fuzzy_score, best_fuzzy_field = score, field

        if best_fuzzy_score >= self.fuzzy_threshold:
            return best_fuzzy_field, best_fuzzy_score / 100, "fuzzy"

        # Pass 2: semantic similarity for non-lexical matches
        col_embedding = self.model.encode(normalized, convert_to_tensor=True)
        sims = util.cos_sim(col_embedding, self.field_embeddings)[0]
        best_idx = int(sims.argmax())
        best_score = float(sims[best_idx])

        if best_score >= self.embedding_threshold:
            return self.field_names[best_idx], best_score, "embedding"

        return None, best_score, "low_confidence"