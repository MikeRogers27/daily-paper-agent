import json
import random
import subprocess

from .llm_client import LLMClient


class GeminiClient(LLMClient):
    def __init__(
        self,
        model: str = "gemini-pro",
        max_retries: int = 3,
        retry_delay: float = 2.0,
        mock_mode: bool = False,
    ):
        super().__init__(max_retries, retry_delay)
        self.model = model
        self.mock_mode = mock_mode

    def _invoke_impl(self, prompt: str, system_prompt: str | None = None) -> str:
        """Gemini-CLI specific implementation."""
        if self.mock_mode:
            return self._mock_invoke(prompt)

        # Combine system prompt and user prompt
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        try:
            result = subprocess.run(
                ["gemini", "-m", self.model, "--prompt", full_prompt],
                capture_output=True,
                text=True,
                timeout=60,
                check=True,
            )
            return result.stdout.strip()

        except FileNotFoundError:
            raise Exception("gemini not found. Please install it first.")
        except subprocess.TimeoutExpired:
            raise Exception("gemini timed out after 60 seconds")
        except subprocess.CalledProcessError as e:
            raise Exception(f"gemini failed: {e.stderr}")

    def _mock_invoke(self, prompt: str) -> str:
        """Mock LLM response for testing."""
        import re

        paper_ids = re.findall(r"Paper ID: ([^\n]+)", prompt)

        if paper_ids:
            scores = {}
            for paper_id in paper_ids:
                prompt_lower = prompt.lower()
                if any(
                    kw in prompt_lower
                    for kw in ["portrait", "face", "talking", "diffusion", "animation"]
                ):
                    scores[paper_id] = random.choice([3, 4, 5])
                else:
                    scores[paper_id] = random.choice([1, 2, 3])

            return json.dumps(scores)
        else:
            return "This paper presents a novel approach to the problem, demonstrating significant improvements over existing methods. The proposed technique shows promising results on benchmark datasets."
