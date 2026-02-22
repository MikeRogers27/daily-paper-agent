# hf_daily_tool.py
import datetime as dt

import requests
from bs4 import BeautifulSoup

from .models import Paper

HF_DAILY_URL_TEMPLATE = "https://huggingface.co/papers/date/{date}"  # YYYY-MM-DD


def _fetch_abstract(paper_url: str) -> str | None:
    """Fetch abstract from paper detail page."""
    try:
        resp = requests.get(paper_url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find the abstract section
        abstract_div = soup.find("h2", string="Abstract")  # type: ignore
        if abstract_div:
            parent = abstract_div.find_parent("div")
            if parent:
                # Find the <p> tag containing the actual abstract text
                abstract_p = parent.find("p", class_="text-gray-600")
                if abstract_p:
                    return str(abstract_p.get_text(strip=True))
        return None
    except Exception:
        return None


def get_hf_daily_papers(day: dt.date) -> list[Paper]:
    """
    Scrape Hugging Face Daily Papers for a given date.
    Fetches abstracts from individual paper pages.
    """
    url = HF_DAILY_URL_TEMPLATE.format(date=day.isoformat())
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    papers: list[Paper] = []

    for article in soup.find_all("article"):
        title_link = article.find("a", href=True, string=True)  # type: ignore
        if not title_link:
            for a in article.find_all("a", href=True):
                if str(a["href"]).startswith("/papers/"):
                    title_link = a
                    break
        if not title_link:
            continue

        href = title_link["href"]
        if not href.startswith("/papers/"):
            continue

        title = title_link.get_text(strip=True)
        if not title:
            continue

        paper_url = "https://huggingface.co" + href
        paper_id = href.rstrip("/").split("/")[-1]

        # Fetch abstract from paper detail page
        abstract = _fetch_abstract(paper_url)

        papers.append(
            Paper(
                id=paper_id,
                title=title,
                authors=[],
                abstract=abstract,
                source="huggingface",
                url=paper_url,
                published_date=day,
            )
        )

    return papers
