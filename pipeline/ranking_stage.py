import json
from pathlib import Path

from config import Config
from pipeline.llm_client import LLMClient, parse_llm_response
from tools.models import Paper

RETRY_FILENAME = "retry_pending.json"


def load_ranking_prompt() -> str:
    """Load the relevance specification document from the given path."""
    return Path("prompts/rank-papers.md").read_text()


def load_relevance_spec(spec_path: str) -> str:
    """Load the relevance specification document from the given path."""
    return Path(spec_path).read_text()


def _paper_to_dict(p: Paper) -> dict:
    """Convert Paper to JSON-serializable dict for retry persistence."""
    return {
        "id": p.id,
        "title": p.title,
        "authors": p.authors,
        "abstract": p.abstract,
        "source": p.source,
        "url": p.url,
        "published_date": p.published_date.isoformat() if p.published_date else None,
        "tags": p.tags,
    }


def _dict_to_paper(d: dict) -> Paper:
    """Convert dict back to Paper object."""
    from datetime import date as date_type

    return Paper(
        id=d["id"],
        title=d["title"],
        authors=d["authors"],
        abstract=d["abstract"],
        source=d["source"],
        url=d["url"],
        published_date=date_type.fromisoformat(d["published_date"]) if d.get("published_date") else None,
        tags=d.get("tags", []),
    )


def _get_retry_path(cache_dir: str) -> Path:
    """Get the path to the retry pending file."""
    return Path(cache_dir) / RETRY_FILENAME


def load_retry_papers(cache_dir: str) -> list[Paper]:
    """Load papers pending retry from previous failed batches."""
    retry_path = _get_retry_path(cache_dir)
    if not retry_path.exists():
        return []
    try:
        with open(retry_path) as f:
            data = json.load(f)
        return [_dict_to_paper(d) for d in data]
    except (json.JSONDecodeError, KeyError):
        return []


def save_retry_papers(papers: list[Paper], cache_dir: str) -> None:
    """Save papers that failed ranking to retry file for next run."""
    retry_path = _get_retry_path(cache_dir)
    retry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(retry_path, "w") as f:
        json.dump([_paper_to_dict(p) for p in papers], f, indent=2)


def clear_retry_papers(cache_dir: str) -> None:
    """Remove the retry file after all papers have been successfully processed."""
    retry_path = _get_retry_path(cache_dir)
    if retry_path.exists():
        retry_path.unlink()


def rank_papers(papers: list[Paper], config: Config, llm_client: LLMClient) -> list[Paper]:
    """
    Rank papers using LLM based on relevance specification.

    Loads any papers pending retry from previous failed batches, merges them
    with the current papers, and attempts ranking. Papers in batches that fail
    are persisted to a retry file for the next run instead of being scored 0.0.

    Args:
        papers: List of papers to rank
        config: Configuration with batch size and other settings
        llm_client: Initialized LLM client for LLM calls

    Returns:
        Successfully scored papers sorted by relevance_score (descending).
        Failed papers are excluded and saved to retry_pending.json.
    """
    cache_dir = config.output.cache_dir

    # Load retry papers from previous failed batches
    retry_papers = load_retry_papers(cache_dir)
    if retry_papers:
        # Merge retry papers, avoiding duplicates by ID
        existing_ids = {p.id for p in papers}
        new_retries = [p for p in retry_papers if p.id not in existing_ids]
        if new_retries:
            papers = papers + new_retries
            print(f"Loaded {len(new_retries)} papers from retry queue")

    if not papers:
        clear_retry_papers(cache_dir)
        return papers

    spec = load_relevance_spec(config.spec.path)
    batch_size = config.llm.batch_size
    failed_papers: list[Paper] = []

    for i in range(0, len(papers), batch_size):
        batch = papers[i : i + batch_size]

        # Build prompt with paper metadata
        papers_text = ""
        for p in batch:
            authors_str = ", ".join(p.authors[:3]) if p.authors else "Unknown"
            if p.authors and len(p.authors) > 3:
                authors_str += " et al."

            papers_text += f"""
Paper ID: {p.id}
Title: {p.title}
Authors: {authors_str}
Abstract: {p.abstract or "N/A"}
URL: {p.url}

"""

        prompt = load_ranking_prompt()
        prompt = prompt.replace("{papers_text}", papers_text).replace("{current_spec}", spec)

        try:
            response = llm_client.invoke(prompt)
            scores = parse_llm_response(response)

            for p in batch:
                if p.id in scores:
                    p.relevance_score = float(scores[p.id])

        except Exception as e:
            print(f"Error ranking batch: {e}")
            failed_papers.extend(batch)

    # Persist failed papers for retry on next run
    if failed_papers:
        save_retry_papers(failed_papers, cache_dir)
        print(f"Saved {len(failed_papers)} papers to retry queue for next run")
    else:
        clear_retry_papers(cache_dir)

    # Only return successfully scored papers
    scored_papers = [p for p in papers if p not in failed_papers]
    scored_papers.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)
    return scored_papers
