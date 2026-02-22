from dataclasses import dataclass
import os

import yaml


@dataclass
class SourcesConfig:
    arxiv_enabled: bool
    arxiv_categories: list[str]
    arxiv_max_results: int
    hf_enabled: bool


@dataclass
class FilterConfig:
    include_keywords: list[str]
    exclude_keywords: list[str]


@dataclass
class BedrockConfig:
    model_id: str
    region: str


@dataclass
class GeminiConfig:
    model: str


@dataclass
class LLMConfig:
    provider: str
    bedrock: BedrockConfig | None
    gemini: GeminiConfig | None
    batch_size: int
    max_retries: int
    retry_delay: float
    mock_mode: bool = False


@dataclass
class OutputConfig:
    top_n: int
    score_threshold: float
    reports_dir: str
    cache_dir: str


@dataclass
class SlackConfig:
    enabled: bool
    webhook_url: str | None
    min_score: float
    channel: str | None = None


@dataclass
class NotificationsConfig:
    slack: SlackConfig


@dataclass
class SpecConfig:
    path: str
    create_papers_path: str | None = None
    test_cases_path: str | None = None
    backup_dir: str | None = None


@dataclass
class Config:
    sources: SourcesConfig
    filter: FilterConfig
    llm: LLMConfig
    output: OutputConfig
    spec: SpecConfig
    notifications: NotificationsConfig | None = None


def load_config(path: str = "config.yaml") -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)

    llm_data = data["llm"]
    provider = llm_data.get(
        "provider", "bedrock"
    )  # Default to bedrock for backward compatibility

    bedrock_config = None
    gemini_config = None

    if "bedrock" in llm_data:
        bedrock_config = BedrockConfig(
            model_id=llm_data["bedrock"]["model_id"],
            region=llm_data["bedrock"]["region"],
        )
    elif provider == "bedrock":
        # Backward compatibility: old config format
        bedrock_config = BedrockConfig(
            model_id=llm_data["bedrock_model_id"],
            region=llm_data["region"],
        )

    if "gemini" in llm_data:
        gemini_config = GeminiConfig(
            model=llm_data["gemini"]["model"],
        )

    # Parse notifications config
    notifications_config = None
    if "notifications" in data:
        notif_data = data["notifications"]
        if "slack" in notif_data:
            slack_data = notif_data["slack"]
            # Support environment variable for webhook URL
            webhook_url = os.environ.get("SLACK_WEBHOOK_URL") or slack_data.get("webhook_url")
            
            slack_config = SlackConfig(
                enabled=slack_data.get("enabled", False),
                webhook_url=webhook_url,
                min_score=slack_data.get("min_score", 4.5),
                channel=slack_data.get("channel"),
            )
            notifications_config = NotificationsConfig(slack=slack_config)

    # Parse spec config
    spec_data = data.get("spec", {})
    spec_config = SpecConfig(
        path=spec_data.get("path", "prompts/spec.example.md"),
        create_papers_path=spec_data.get("create_papers_path"),
        test_cases_path=spec_data.get("test_cases_path"),
        backup_dir=spec_data.get("backup_dir"),
    )

    return Config(
        sources=SourcesConfig(
            arxiv_enabled=data["sources"]["arxiv"]["enabled"],
            arxiv_categories=data["sources"]["arxiv"]["categories"],
            arxiv_max_results=data["sources"]["arxiv"]["max_results"],
            hf_enabled=data["sources"]["huggingface"]["enabled"],
        ),
        filter=FilterConfig(
            include_keywords=data["filter"]["include_keywords"],
            exclude_keywords=data["filter"]["exclude_keywords"],
        ),
        llm=LLMConfig(
            provider=provider,
            bedrock=bedrock_config,
            gemini=gemini_config,
            batch_size=llm_data["batch_size"],
            max_retries=llm_data["max_retries"],
            retry_delay=llm_data["retry_delay"],
            mock_mode=llm_data.get("mock_mode", False),
        ),
        output=OutputConfig(
            top_n=data["output"]["top_n"],
            score_threshold=data["output"]["score_threshold"],
            reports_dir=data["output"]["reports_dir"],
            cache_dir=data["output"]["cache_dir"],
        ),
        spec=spec_config,
        notifications=notifications_config,
    )
