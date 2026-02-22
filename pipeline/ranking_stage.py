from pathlib import Path

from config import Config
from pipeline.llm_client import LLMClient, parse_llm_response
from tools.models import Paper


def load_ranking_prompt() -> str:
    """Load the relevance specification document from the given path."""
    return Path("prompts/rank-papers.md").read_text()


def load_relevance_spec(spec_path: str) -> str:
    """Load the relevance specification document from the given path."""
    return Path(spec_path).read_text()


def rank_papers(
    papers: list[Paper], config: Config, llm_client: LLMClient
) -> list[Paper]:
    """
    Rank papers using LLM based on relevance specification.

    Args:
        papers: List of papers to rank
        config: Configuration with batch size and other settings
        llm_client: Initialized LLM client for LLM calls

    Returns:
        Papers sorted by relevance_score (descending), with scores populated
    """
    if not papers:
        return papers

    spec = load_relevance_spec(config.spec.path)
    batch_size = config.llm.batch_size

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
        prompt = prompt.replace("{papers_text}", papers_text).replace(
            "{current_spec}", spec
        )

        try:
            response = llm_client.invoke(prompt)
            scores = parse_llm_response(response)

            for p in batch:
                if p.id in scores:
                    p.relevance_score = float(scores[p.id])

        except Exception as e:
            print(f"Error ranking batch: {e}")
            for p in batch:
                p.relevance_score = 0.0

    # Sort by score descending
    papers.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)
    return papers
