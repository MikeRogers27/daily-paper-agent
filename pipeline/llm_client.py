import json
import time
from abc import ABC, abstractmethod
from typing import Any


def parse_llm_response(response_text: str) -> Any:
    """Extract JSON from LLM response text."""
    # Try to find JSON in code blocks
    if "```json" in response_text:
        start = response_text.find("```json") + 7
        end = response_text.find("```", start)
        json_text = response_text[start:end].strip()
    elif "```" in response_text:
        start = response_text.find("```") + 3
        end = response_text.find("```", start)
        json_text = response_text[start:end].strip()
    else:
        json_text = response_text.strip()

    return json.loads(json_text)


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 2.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    @abstractmethod
    def _invoke_impl(self, prompt: str, system_prompt: str | None = None) -> str:
        """Provider-specific implementation of LLM invocation."""
        pass

    def invoke(self, prompt: str, system_prompt: str | None = None) -> str:
        """Invoke LLM with retry logic."""
        for attempt in range(self.max_retries):
            try:
                return self._invoke_impl(prompt, system_prompt)
            except Exception:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
                    time.sleep(delay)
                    continue
                raise

        raise Exception(f"Failed after {self.max_retries} retries")
