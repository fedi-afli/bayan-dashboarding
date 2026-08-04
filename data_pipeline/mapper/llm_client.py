import json
from typing import Optional, Literal
import outlines
from transformers import AutoModelForCausalLM, AutoTokenizer
from pydantic import create_model


class HuggingFaceClient:
    """
    LLM client that uses constrained (grammar-guided) decoding instead of
    free-text generation + regex parsing.
    """

    def __init__(self, model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"):
        # outlines >=1.0 requires an already-loaded HF model + tokenizer,
        # and the loader is now a top-level function, not outlines.models.transformers(...)
        self.model = outlines.from_transformers(
            AutoModelForCausalLM.from_pretrained(model_name),
            AutoTokenizer.from_pretrained(model_name),
        )

    @staticmethod
    def _build_schema(column_names: list[str], allowed_fields: list[str]):
        if not allowed_fields:
            allowed_fields = ["__no_fields_available__"]

        FieldValue = Optional[Literal[tuple(allowed_fields)]]
        fields = {name: (FieldValue, ...) for name in column_names}
        return create_model("ColumnMapping", **fields)

    def generate_mapping(
        self,
        prompt: str,
        column_names: list[str],
        allowed_fields: list[str],
    ) -> dict:
        schema = self._build_schema(column_names, allowed_fields)

        # outlines >=1.0: call the wrapped model directly with the output
        # type as an argument, instead of outlines.generate.json(model, schema)
        raw_json = self.model(prompt, schema, max_new_tokens=512)

        # it now returns a raw JSON string, not a Pydantic instance
        return json.loads(raw_json)