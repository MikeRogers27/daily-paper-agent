#!/usr/bin/env python3
"""
Testing framework for relevance scoring.

Usage:
    python -m tools.test_scoring test --test-file test-cases.yaml
    python -m tools.test_scoring export-failures --test-file test-cases.yaml
"""

import argparse
import json
import math
from dataclasses import dataclass, field
from typing import Any

import yaml

from config import Config, load_config
from pipeline.llm_client import LLMClient
from pipeline.ranking_stage import rank_papers
from tools.models import Paper


@dataclass
class TestCase:
    id: str
    title: str
    abstract: str
    expected_score: float
    notes: str = ""
    authors: list[str] = field(default_factory=list)
    url: str = ""


def load_test_cases(test_file: str) -> list[TestCase]:
    """Load test cases from YAML file."""
    with open(test_file) as f:
        data = yaml.safe_load(f)

    cases = []
    for tc in data.get("test_cases", []):
        cases.append(
            TestCase(
                id=tc["id"],
                title=tc["title"],
                abstract=tc.get("abstract", ""),
                expected_score=tc["expected_score"],
                notes=tc.get("notes", ""),
                authors=tc.get("authors", []),
                url=tc.get("url", ""),
            )
        )
    return cases


def test_case_to_paper(tc: TestCase) -> Paper:
    """Convert TestCase to Paper for scoring."""
    return Paper(
        id=tc.id,
        title=tc.title,
        authors=tc.authors,
        abstract=tc.abstract,
        source="test",
        url=tc.url or f"https://arxiv.org/abs/{tc.id}",
        published_date=None,
        tags=[],
        relevance_score=None,
        summary=None,
    )


def score_test_cases(test_cases: list[TestCase], config: Config, llm_client: LLMClient) -> dict[str, float]:
    """Score test cases using rank_papers."""
    papers = [test_case_to_paper(tc) for tc in test_cases]
    ranked_papers = rank_papers(papers, config, llm_client)

    actual_scores = {}
    for paper in ranked_papers:
        actual_scores[paper.id] = paper.relevance_score or 0.0

    return actual_scores


def compare_scores(test_cases: list[TestCase], actual_scores: dict[str, float]) -> dict[str, Any]:
    """Calculate metrics and identify failures."""
    errors = []
    failures = []

    for tc in test_cases:
        actual = actual_scores.get(tc.id, 0)
        expected = tc.expected_score
        error = abs(actual - expected)
        errors.append(error)

        if error > 1.0:
            failures.append(
                {
                    "id": tc.id,
                    "title": tc.title,
                    "abstract": tc.abstract,
                    "expected": expected,
                    "actual": actual,
                    "diff": actual - expected,
                }
            )

    mae = sum(errors) / len(errors) if errors else 0
    rmse = math.sqrt(sum(e**2 for e in errors) / len(errors)) if errors else 0
    accuracy = sum(1 for e in errors if e <= 0.5) / len(errors) if errors else 0

    return {"mae": mae, "rmse": rmse, "accuracy": accuracy, "failures": failures}


def generate_test_report(
    comparison: dict[str, Any], test_cases: list[TestCase], actual_scores: dict[str, float]
) -> None:
    """Generate formatted test report."""
    print("\\n" + "=" * 60)
    print("SCORING TEST REPORT")
    print("=" * 60)

    print(f"\\nTotal test cases: {len(test_cases)}")
    print(f"Mean Absolute Error: {comparison['mae']:.2f}")
    print(f"Root Mean Square Error: {comparison['rmse']:.2f}")
    print(f"Accuracy (±0.5): {comparison['accuracy'] * 100:.1f}%")

    print(f"\\nFailures (error > 1.0): {len(comparison['failures'])}")

    if comparison["failures"]:
        print("\\n" + "-" * 60)
        print("FAILED TEST CASES")
        print("-" * 60)
        for f in comparison["failures"]:
            print(f"\\nID: {f['id']}")
            print(f"Title: {f['title'][:60]}...")
            print(f"Expected: {f['expected']:.1f} | Actual: {f['actual']:.1f} | Diff: {f['diff']:+.1f}")

    print("\\n" + "=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="Test relevance scoring")
    parser.add_argument("command", choices=["test", "export-failures"])
    parser.add_argument("--test-file", help="Path to test cases YAML (overrides config)")
    parser.add_argument("--export", help="Export failures to JSON file")

    args = parser.parse_args()

    config = load_config()

    test_file = args.test_file or config.spec.test_cases_path
    if not test_file:
        parser.error("--test-file must be specified or spec.test_cases_path must be set in config.yaml")

    test_cases = load_test_cases(test_file)

    if args.command == "test":
        from pipeline.llm_factory import create_llm_client

        llm_client = create_llm_client(config)
        actual_scores = score_test_cases(test_cases, config, llm_client)
        comparison = compare_scores(test_cases, actual_scores)
        generate_test_report(comparison, test_cases, actual_scores)

        if args.export and comparison["failures"]:
            with open(args.export, "w") as f:
                json.dump(comparison["failures"], f, indent=2)
            print(f"\nExported failures to: {args.export}")


if __name__ == "__main__":
    main()
