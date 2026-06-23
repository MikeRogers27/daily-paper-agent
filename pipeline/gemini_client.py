import json
import random
import re

import requests

from .llm_client import LLMClient

_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiClient(LLMClient):
    def __init__(
        self,
        model: str = "gemini-2.5-flash-lite",
        api_key: str = "",
        max_retries: int = 3,
        retry_delay: float = 2.0,
        mock_mode: bool = False,
    ):
        super().__init__(max_retries, retry_delay)
        self.model = model
        self.mock_mode = mock_mode
        if not mock_mode:
            self.api_key = api_key
            if not self.api_key:
                raise ValueError(
                    "Gemini api_key is not set in config.yaml. "
                    "Get an API key from https://aistudio.google.com/apikey"
                )

    def _invoke_impl(self, prompt: str, system_prompt: str | None = None) -> str:
        if self.mock_mode:
            return self._mock_invoke(prompt)

        url = f"{_API_BASE}/{self.model}:generateContent?key={self.api_key}"

        body: dict = {"contents": [{"parts": [{"text": prompt}]}]}
        if system_prompt:
            body["system_instruction"] = {"parts": [{"text": system_prompt}]}

        resp = requests.post(url, json=body, timeout=120)
        resp.raise_for_status()

        payload = resp.json()
        return payload["candidates"][0]["content"]["parts"][0]["text"]

    def _mock_invoke(self, prompt: str) -> str:
        """Mock LLM response for testing."""
        paper_ids = re.findall(r"Paper ID: ([^\n]+)", prompt)

        if paper_ids:
            scores = {}
            for paper_id in paper_ids:
                prompt_lower = prompt.lower()
                if any(kw in prompt_lower for kw in ["portrait", "face", "talking", "diffusion", "animation"]):
                    scores[paper_id] = random.choice([3, 4, 5])
                else:
                    scores[paper_id] = random.choice([1, 2, 3])

            return json.dumps(scores)
        else:
            return "This paper presents a novel approach to the problem, demonstrating significant improvements over existing methods. The proposed technique shows promising results on benchmark datasets."
