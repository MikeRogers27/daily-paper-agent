from config import Config

from .bedrock_client import BedrockClient
from .gemini_client import GeminiClient
from .llm_client import LLMClient


def create_llm_client(config: Config) -> LLMClient:
    """Factory function to create LLM client based on config."""

    provider = config.llm.provider

    if provider == "bedrock":
        if not config.llm.bedrock:
            raise ValueError("Bedrock provider selected but bedrock config is missing")

        return BedrockClient(
            model_id=config.llm.bedrock.model_id,
            region=config.llm.bedrock.region,
            max_retries=config.llm.max_retries,
            retry_delay=config.llm.retry_delay,
            mock_mode=config.llm.mock_mode,
        )

    elif provider == "gemini":
        if not config.llm.gemini:
            raise ValueError("Gemini provider selected but gemini config is missing")

        return GeminiClient(
            model=config.llm.gemini.model,
            max_retries=config.llm.max_retries,
            retry_delay=config.llm.retry_delay,
            mock_mode=config.llm.mock_mode,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Must be 'bedrock' or 'gemini'")
