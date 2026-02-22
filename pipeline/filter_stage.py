from config import Config
from tools.models import Paper


def filter_papers(papers: list[Paper], config: Config) -> list[Paper]:
    """
    Filter papers by keyword matching on title and abstract.

    Args:
        papers: List of papers to filter
        config: Configuration with include/exclude keywords

    Returns:
        Filtered list of papers matching include keywords and not matching exclude keywords
    """
    filtered = []

    for paper in papers:
        text = (paper.title + " " + (paper.abstract or "")).lower()

        # Check exclude keywords first
        if any(kw.lower() in text for kw in config.filter.exclude_keywords):
            continue

        # Check include keywords
        if any(kw.lower() in text for kw in config.filter.include_keywords):
            filtered.append(paper)

    return filtered
