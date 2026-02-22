# tools_api.py
import datetime as dt
from typing import Dict, Any, List

from tools.models import Paper
from tools.arxiv_tool import get_arxiv_papers_for_date
from tools.hf_daily_tool import get_hf_daily_papers

def _paper_to_dict(p: Paper) -> Dict[str, Any]:
    return {
        "id": p.id,
        "title": p.title,
        "authors": p.authors,
        "abstract": p.abstract,
        "source": p.source,
        "url": p.url,
        "published_date": p.published_date.isoformat() if p.published_date else None,
    }

def tool_get_daily_papers(date_str: str) -> Dict[str, List[Dict[str, Any]]]:
    day = dt.date.fromisoformat(date_str)
    arxiv_papers = get_arxiv_papers_for_date(day)
    hf_papers = get_hf_daily_papers(day)

    return {
        "arxiv": [_paper_to_dict(p) for p in arxiv_papers],
        "huggingface": [_paper_to_dict(p) for p in hf_papers],
    }
