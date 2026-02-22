import json
from datetime import date
from pathlib import Path

from tools.models import Paper


def generate_json_report(papers: list[Paper], report_date: date, output_path: str):
    """Generate structured JSON report."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    report = {
        "date": report_date.isoformat(),
        "paper_count": len(papers),
        "papers": [
            {
                "id": p.id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "source": p.source,
                "url": p.url,
                "published_date": p.published_date.isoformat()
                if p.published_date
                else None,
                "tags": p.tags,
                "relevance_score": p.relevance_score,
                "summary": p.summary,
            }
            for p in papers
        ],
    }

    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)


def generate_markdown_report(papers: list[Paper], report_date: date, output_path: str):
    """Generate human-readable Markdown report."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Group papers by score tier
    tier_5 = [p for p in papers if (p.relevance_score or 0) >= 5]
    tier_4 = [p for p in papers if 4 <= (p.relevance_score or 0) < 5]
    tier_3 = [p for p in papers if 3 <= (p.relevance_score or 0) < 4]
    tier_others = [p for p in papers if (p.relevance_score or 0) < 3]

    lines = [
        f"# Daily Paper Report - {report_date.isoformat()}",
        "",
        f"**Total Papers:** {len(papers)}",
        "",
    ]

    if tier_5:
        lines.extend(
            [
                "## ⭐ Must-Read Papers (Score: 5)",
                "",
            ]
        )
        for p in tier_5:
            lines.extend(_format_paper(p))

    if tier_4:
        lines.extend(
            [
                "## 🔥 Highly Relevant Papers (Score: 4)",
                "",
            ]
        )
        for p in tier_4:
            lines.extend(_format_paper(p))

    if tier_3:
        lines.extend(
            [
                "## 📄 Relevant Papers (Score: 3)",
                "",
            ]
        )
        for p in tier_3:
            lines.extend(_format_paper(p))

    if tier_others:
        lines.extend(
            [
                "## 🗑️ Other Papers (Score: <3)",
                "",
            ]
        )
        for p in tier_others:
            lines.extend(_format_paper(p))

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


def _format_paper(p: Paper) -> list[str]:
    """Format a single paper for Markdown output."""
    authors_str = ", ".join(p.authors[:3]) if p.authors else "Unknown"
    if p.authors and len(p.authors) > 3:
        authors_str += " et al."

    lines = [
        f"### [{p.title}]({p.url})",
        "",
        f"**Authors:** {authors_str}",
        "",
        f"**Score:** {p.relevance_score:.1f} | **Source:** {p.source}",
        "",
    ]

    if p.summary:
        lines.extend(
            [
                f"**Summary:** {p.summary}",
                "",
            ]
        )

    if p.tags:
        lines.extend(
            [
                f"**Tags:** {', '.join(p.tags)}",
                "",
            ]
        )

    lines.append("---")
    lines.append("")

    return lines
