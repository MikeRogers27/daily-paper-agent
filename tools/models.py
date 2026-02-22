from dataclasses import dataclass, field
from datetime import date


@dataclass
class Paper:
    id: str
    title: str
    authors: list[str]
    abstract: str | None
    source: str
    url: str
    published_date: date | None
    tags: list[str] = field(default_factory=list)
    relevance_score: float | None = None
    summary: str | None = None
