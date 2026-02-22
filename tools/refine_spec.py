#!/usr/bin/env python3
"""
Spec refinement tool - refines relevance specification based on feedback papers.

Usage:
    python -m tools.refine_spec --spec path/to/spec.md \\
        --underscored papers.json --overscored papers.json \\
        --output refined-spec.md
"""

import argparse
import json
from pathlib import Path

from config import load_config
from pipeline.llm_client import create_llm_client


def load_feedback_papers(filepath):
    """Load papers from JSON file."""
    with open(filepath) as f:
        return json.load(f)


def load_refine_prompt():
    """Load the refinement prompt template."""
    return Path("prompts/refine-spec.md").read_text()


def format_papers_for_prompt(papers):
    """Format paper list for LLM prompt."""
    lines = []
    for p in papers:
        lines.append(f"Title: {p['title']}")
        lines.append(f"Abstract: {p.get('abstract', 'N/A')}")
        lines.append(f"Actual Score: {p.get('actual_score', 'N/A')}")
        lines.append(f"Expected Score: {p.get('expected_score', 'N/A')}")
        lines.append("")
    return "\n".join(lines)


def refine_spec(spec_path, underscored_file, overscored_file, llm_client):
    """Refine spec based on feedback papers."""
    # Load current spec
    current_spec = Path(spec_path).read_text()

    # Load feedback papers
    underscored = load_feedback_papers(underscored_file) if underscored_file else []
    overscored = load_feedback_papers(overscored_file) if overscored_file else []

    # Load refinement prompt
    prompt_template = load_refine_prompt()

    # Format prompt
    prompt = prompt_template.format(
        current_spec=current_spec,
        underscored_papers=format_papers_for_prompt(underscored),
        overscored_papers=format_papers_for_prompt(overscored),
    )

    # Call LLM
    refined_spec = llm_client.invoke(prompt)

    return refined_spec


def save_refined_spec(spec_text, output_path):
    """Save refined spec to file."""
    Path(output_path).write_text(spec_text)
    print(f"Saved refined spec to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Refine relevance specification")
    parser.add_argument("--spec", required=True, help="Path to current spec")
    parser.add_argument("--underscored", help="JSON file with underscored papers")
    parser.add_argument("--overscored", help="JSON file with overscored papers")
    parser.add_argument("--output", required=True, help="Output path for refined spec")

    args = parser.parse_args()

    config = load_config()
    llm_client = create_llm_client(config)

    refined = refine_spec(args.spec, args.underscored, args.overscored, llm_client)
    save_refined_spec(refined, args.output)


if __name__ == "__main__":
    main()
