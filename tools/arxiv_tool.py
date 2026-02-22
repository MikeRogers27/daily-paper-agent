# arxiv_tool.py
import datetime as dt

import feedparser
import requests

from .models import Paper

ARXIV_API_URL = "http://export.arxiv.org/api/query"


def _format_arxiv_date_range(day: dt.date) -> str:
    """
    Build a lastUpdatedDate range [YYYYMMDD000000 TO YYYYMMDD235959] in UTC.
    """
    start = day.strftime("%Y%m%d") + "000000"
    end = day.strftime("%Y%m%d") + "235959"
    return f"lastUpdatedDate:[{start} TO {end}]"


def get_arxiv_papers_for_date(
    day: dt.date,
    categories=("cs.CV", "cs.AI"),
    max_results: int = 200,
) -> list[Paper]:
    """
    Fetch arXiv papers updated on a given UTC day for the specified categories.
    """
    date_range = _format_arxiv_date_range(day)
    cat_query = " OR ".join(f"cat:{c}" for c in categories)
    search_query = f"({cat_query}) AND {date_range}"

    params = {
        "search_query": "'" + search_query + "'",
        "start": 0,
        "max_results": max_results,
        "sortBy": "lastUpdatedDate",
    }

    resp = requests.get(ARXIV_API_URL, params=params, timeout=30)
    resp.raise_for_status()

    feed = feedparser.parse(resp.text)

    papers: list[Paper] = []
    for entry in feed.entries:
        arxiv_id = entry.id.split("/abs/")[-1]
        title = entry.title.strip().replace("\n", " ")
        summary = entry.summary.strip()
        authors = [a.name for a in entry.authors] if "authors" in entry else []

        # published/updated fields are ISO timestamps
        pub_date = None
        if "published" in entry:
            pub_date = dt.date.fromisoformat(entry.published[:10])

        paper = Paper(
            id=arxiv_id,
            title=title,
            authors=authors,
            abstract=summary,
            source="arxiv",
            url=f"https://arxiv.org/abs/{arxiv_id}",
            published_date=pub_date,
        )
        papers.append(paper)

    return papers
