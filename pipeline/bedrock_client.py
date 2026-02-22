import json
import random

import boto3

from .llm_client import LLMClient


class BedrockClient(LLMClient):
    def __init__(
        self,
        model_id: str,
        region: str,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        mock_mode: bool = False,
    ):
        super().__init__(max_retries, retry_delay)
        self.model_id = model_id
        self.mock_mode = mock_mode

        if not mock_mode:
            self.client = boto3.client("bedrock-runtime", region_name=region)

    def _invoke_impl(self, prompt: str, system_prompt: str | None = None) -> str:
        """Bedrock-specific implementation."""
        if self.mock_mode:
            return self._mock_invoke(prompt)

        messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": messages,
        }

        if system_prompt:
            body["system"] = system_prompt

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body),
        )

        response_body = json.loads(response["body"].read())
        return str(response_body["content"][0]["text"])

    def _mock_invoke(self, prompt: str) -> str:
        """Mock LLM response for testing."""
        import re

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
