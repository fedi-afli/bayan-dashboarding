import json
import threading
from typing import Optional, Literal

import outlines
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from pydantic import create_model


class HuggingFaceClient:
    """
    LLM client that uses constrained (grammar-guided) decoding instead of
    free-text generation + regex parsing.
    """

    def __init__(self, model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"):
        use_cuda = torch.cuda.is_available()
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=torch.float16 if use_cuda else torch.float32,
            device_map="cuda" if use_cuda else None,
        )
        self.model = outlines.from_transformers(model, AutoTokenizer.from_pretrained(model_name))
        # one generation at a time: requests run in a threadpool now, and
        # the HF model isn't safe to call concurrently
        self._lock = threading.Lock()

    @staticmethod
    def _build_schema(allowed_by_column: dict[str, list[str]]):
        fields = {}
        for name, allowed in allowed_by_column.items():
            choices = tuple(allowed) or ("__no_fields_available__",)
            fields[name] = (Optional[Literal[choices]], ...)
        return create_model("ColumnMapping", **fields)

    def generate_mapping(self, prompt: str, allowed_by_column: dict[str, list[str]]) -> dict:
        """
        allowed_by_column: {column_name: [schema fields this column may map to]}
        — restricting per column means the model physically can't answer
        with a type-incompatible field.
        """
        schema = self._build_schema(allowed_by_column)
        with self._lock:
            raw_json = self.model(prompt, schema, max_new_tokens=512)
        return json.loads(raw_json)
