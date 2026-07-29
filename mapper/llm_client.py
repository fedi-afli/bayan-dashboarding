from transformers import pipeline


class HuggingFaceClient:
    def __init__(self):
        self.model = pipeline(
            "text-generation",
            model="Qwen/Qwen2.5-1.5B-Instruct"
        )

    def generate(self, prompt):
        messages = [{"role": "user", "content": prompt}]
        result = self.model(
            messages,
            max_new_tokens=200,
            do_sample=False,
        )
        return result[0]["generated_text"][-1]["content"]