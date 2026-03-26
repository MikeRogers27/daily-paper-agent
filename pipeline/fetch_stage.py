import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from config import Config
from tools.arxiv_tool import get_arxiv_papers_for_date
from tools.hf_daily_tool import get_hf_daily_papers
from tools.models import Paper


def _normalize_arxiv_id(raw_id: str) -> str:
    """Strip version suffix (e.g. 'v1') and extract base arXiv ID."""
    match = re.search(r"(\d{4}\.\d{4,5})", raw_id)
    return match.group(1) if match else raw_id


def _extract_arxiv_id(url: str) -> str | None:
    """Extract arXiv ID from URL or paper ID."""
    match = re.search(r"(\d{4}\.\d{4,5})", url)
    return match.group(1) if match else None


def _load_previously_reported_ids(reports_dir: str) -> set[str]:
    """Load normalized paper IDs from all existing report JSON files."""
    reported: set[str] = set()
    reports_path = Path(reports_dir)
    if not reports_path.exists():
        return reported
    for report_file in reports_path.glob("*.json"):
        try:
            with open(report_file) as f:
                data = json.load(f)
            papers = data if isinstance(data, list) else data.get("papers", [])
            for p in papers:
                reported.add(_normalize_arxiv_id(p["id"]))
        except (json.JSONDecodeError, KeyError):
            continue
    return reported


def fetch_papers(day: date, config: Config, *, allow_duplicates: bool = False) -> list[Paper]:
    """
    Fetch papers from all enabled sources and deduplicate.

    Deduplicates within the day (arXiv vs HuggingFace) and across
    previous days (skips papers already in past reports).

    Args:
        day: Date to fetch papers for
        config: Configuration object with source settings
        allow_duplicates: If True, skip cross-day deduplication

    Returns:
        List of Paper objects, deduplicated by normalized arXiv ID
    """
    previously_reported = (
        set() if allow_duplicates
        else _load_previously_reported_ids(config.output.reports_dir)
    )

    papers = []
    arxiv_ids = set()

    if config.sources.arxiv_enabled:
        arxiv_papers = get_arxiv_papers_for_date(
            day,
            categories=tuple(config.sources.arxiv_categories),
            max_results=config.sources.arxiv_max_results,
        )
        for p in arxiv_papers:
            norm_id = _normalize_arxiv_id(p.id)
            if norm_id not in previously_reported:
                papers.append(p)
                arxiv_ids.add(norm_id)

    if config.sources.hf_enabled:
        hf_papers = get_hf_daily_papers(day)
        for p in hf_papers:
            arxiv_id = _extract_arxiv_id(p.url) or _extract_arxiv_id(p.id)
            norm_id = _normalize_arxiv_id(arxiv_id) if arxiv_id else None
            if norm_id and (norm_id in arxiv_ids or norm_id in previously_reported):
                continue
            papers.append(p)

    return papers


def _paper_to_dict(p: Paper) -> dict[str, Any]:
    """Convert Paper to JSON-serializable dict."""
    return {
        "id": p.id,
        "title": p.title,
        "authors": p.authors,
        "abstract": p.abstract,
        "source": p.source,
        "url": p.url,
        "published_date": p.published_date.isoformat() if p.published_date else None,
        "tags": p.tags,
        "relevance_score": p.relevance_score,
        "summary": p.summary,
    }


def _dict_to_paper(d: dict[str, Any]) -> Paper:
    """Convert dict to Paper object."""
    return Paper(
        id=d["id"],
        title=d["title"],
        authors=d["authors"],
        abstract=d["abstract"],
        source=d["source"],
        url=d["url"],
        published_date=date.fromisoformat(d["published_date"]) if d["published_date"] else None,
        tags=d.get("tags", []),
        relevance_score=d.get("relevance_score"),
        summary=d.get("summary"),
    )


def save_papers_cache(papers: list[Paper], cache_path: str) -> None:
    """Save papers to JSON cache file."""
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump([_paper_to_dict(p) for p in papers], f, indent=2)


def load_papers_cache(cache_path: str) -> list[Paper]:
    """Load papers from JSON cache file."""
    with open(cache_path) as f:
        data = json.load(f)
    return [_dict_to_paper(d) for d in data]
