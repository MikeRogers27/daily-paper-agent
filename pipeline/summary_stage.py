from config import Config
from pipeline.llm_client import LLMClient
from tools.models import Paper


def select_top_papers(papers: list[Paper], config: Config) -> list[Paper]:
    """
    Select top papers using hybrid logic: top N OR score >= threshold.

    Args:
        papers: List of ranked papers (should be sorted by score)
        config: Configuration with top_n and score_threshold

    Returns:
        Union of top N papers and papers with score >= threshold
    """
    if not papers:
        return []

    # Get top N by score
    top_n = papers[: config.output.top_n]

    # Get all papers with score >= threshold
    high_score = [
        p for p in papers if (p.relevance_score or 0) >= config.output.score_threshold
    ]

    # Return union (deduplicated by ID)
    seen = set()
    result = []
    for p in top_n + high_score:
        if p.id not in seen:
            seen.add(p.id)
            result.append(p)

    # Sort by score descending
    result.sort(key=lambda p: p.relevance_score or 0.0, reverse=True)
    return result


def generate_summaries(papers: list[Paper], llm_client: LLMClient) -> list[Paper]:
    """
    Generate summaries for selected papers.

    Args:
        papers: List of papers to summarize
        llm_client: Initialized LLM client for LLM calls

    Returns:
        Papers with summary field populated (falls back to truncated abstract on error)
    """
    for paper in papers:
        if not paper.abstract:
            paper.summary = "No abstract available."
            continue

        prompt = f"""Summarize this academic paper in 2-3 sentences. Focus on the key contribution and methodology.

Title: {paper.title}
Abstract: {paper.abstract}

Provide only the summary, no other text."""

        try:
            summary = llm_client.invoke(prompt)
            paper.summary = summary.strip()
        except Exception as e:
            print(f"Error generating summary for {paper.id}: {e}")
            paper.summary = (
                paper.abstract[:200] + "..."
                if len(paper.abstract) > 200
                else paper.abstract
            )

    return papers
