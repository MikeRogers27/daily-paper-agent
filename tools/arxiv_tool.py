import datetime as dt
import xml.etree.ElementTree as ET

import requests

from .models import Paper

ARXIV_OAI_URL = "http://export.arxiv.org/oai2"

_OAI_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "arxiv": "http://arxiv.org/OAI/arXiv/",
}


def _category_to_oai_set(category: str) -> str:
    """Convert arXiv category (e.g. 'cs.CV') to OAI-PMH set (e.g. 'cs:cs:CV')."""
    parts = category.split(".")
    return f"{parts[0]}:{category.replace('.', ':')}"


def _parse_oai_record(record: ET.Element) -> Paper | None:
    """Parse an OAI-PMH record into a Paper."""
    header = record.find("oai:header", _OAI_NS)
    if header is None:
        return None
    identifier = header.find("oai:identifier", _OAI_NS)
    if identifier is None or identifier.text is None:
        return None
    arxiv_id = identifier.text.split(":")[-1]

    meta = record.find(".//arxiv:arXiv", _OAI_NS)
    if meta is None:
        return None

    title_el = meta.find("arxiv:title", _OAI_NS)
    title = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else ""

    abstract_el = meta.find("arxiv:abstract", _OAI_NS)
    abstract = abstract_el.text.strip() if abstract_el is not None and abstract_el.text else ""

    authors: list[str] = []
    for author in meta.findall("arxiv:authors/arxiv:author", _OAI_NS):
        fn = author.find("arxiv:forenames", _OAI_NS)
        kn = author.find("arxiv:keyname", _OAI_NS)
        name = f"{fn.text} {kn.text}" if fn is not None and fn.text else (kn.text if kn is not None else "")
        if name:
            authors.append(name)

    created = meta.find("arxiv:created", _OAI_NS)
    pub_date = dt.date.fromisoformat(created.text) if created is not None and created.text else None

    return Paper(
        id=arxiv_id,
        title=title,
        authors=authors,
        abstract=abstract,
        source="arxiv",
        url=f"https://arxiv.org/abs/{arxiv_id}",
        published_date=pub_date,
    )


def _fetch_oai_records(oai_date: str, oai_set: str) -> list[ET.Element]:
    """Fetch all OAI-PMH records for a date and set, handling pagination."""
    records: list[ET.Element] = []
    params: dict[str, str] = {
        "verb": "ListRecords",
        "metadataPrefix": "arXiv",
        "from": oai_date,
        "until": oai_date,
        "set": oai_set,
    }

    while True:
        resp = requests.get(ARXIV_OAI_URL, params=params, timeout=60)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        records.extend(root.findall(".//oai:record", _OAI_NS))

        token = root.find(".//oai:resumptionToken", _OAI_NS)
        if token is not None and token.text:
            params = {"verb": "ListRecords", "resumptionToken": token.text}
        else:
            break

    return records


def get_arxiv_papers_for_date(
    day: dt.date,
    categories: list[str] | None = None,
    max_results: int = 200,
) -> list[Paper]:
    """
    Fetch arXiv papers for a given day using the OAI-PMH API.

    OAI-PMH datestamps are offset by +1 day from the paper's update date,
    so we query day+1 to match papers updated on the requested day.
    """
    if categories is None:
        categories = ["cs.CV", "cs.AI"]

    oai_date = (day + dt.timedelta(days=1)).isoformat()

    seen: set[str] = set()
    papers: list[Paper] = []
    for cat in categories:
        oai_set = _category_to_oai_set(cat)
        for record in _fetch_oai_records(oai_date, oai_set):
            paper = _parse_oai_record(record)
            if paper and paper.id not in seen:
                seen.add(paper.id)
                papers.append(paper)

    return papers
