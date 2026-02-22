#!/usr/bin/env python3
"""
Testing framework for relevance scoring.

Usage:
    python -m tools.test_scoring test --test-file test-cases.yaml
    python -m tools.test_scoring export-failures --test-file test-cases.yaml
"""

import argparse
import math
from dataclasses import dataclass

import yaml

from config import load_config
from pipeline.bedrock_client import parse_llm_response
from pipeline.llm_client import create_llm_client
from pipeline.ranking_stage import load_relevance_spec


@dataclass
class TestCase:
    id: str
    title: str
    abstract: str
    expected_score: float
    notes: str = ""


def load_test_cases(test_file):
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
            )
        )
    return cases


def score_test_cases(test_cases, spec_path, llm_client):
    """Score test cases using the spec."""
    spec = load_relevance_spec(spec_path)
    actual_scores = {}

    for tc in test_cases:
        prompt = f"""Rate this paper on a 1-5 scale based on the relevance specification.

Paper ID: {tc.id}
Title: {tc.title}
Abstract: {tc.abstract}

Return JSON: {{"score": <number>}}"""

        try:
            response = llm_client.invoke(prompt, system_prompt=spec)
            result = parse_llm_response(response)
            actual_scores[tc.id] = float(result.get("score", 0))
        except Exception as e:
            print(f"Error scoring {tc.id}: {e}")
            actual_scores[tc.id] = 0.0

    return actual_scores


def compare_scores(test_cases, actual_scores):
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


def generate_test_report(comparison, test_cases, actual_scores):
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
            print(
                f"Expected: {f['expected']:.1f} | Actual: {f['actual']:.1f} | Diff: {f['diff']:+.1f}"
            )

    print("\\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Test relevance scoring")
    parser.add_argument("command", choices=["test", "export-failures"])
    parser.add_argument("--test-file", required=True, help="Path to test cases YAML")
    parser.add_argument("--spec-path", help="Path to spec (default from config)")
    parser.add_argument("--export", help="Export failures to JSON file")

    args = parser.parse_args()

    config = load_config()
    spec_path = args.spec_path or config.spec.path

    test_cases = load_test_cases(args.test_file)

    if args.command == "test":
        llm_client = create_llm_client(config)
        actual_scores = score_test_cases(test_cases, spec_path, llm_client)
        comparison = compare_scores(test_cases, actual_scores)
        generate_test_report(comparison, test_cases, actual_scores)

        if args.export and comparison["failures"]:
            with open(args.export, "w") as f:
                json.dump(comparison["failures"], f, indent=2)
            print(f"\\nExported failures to: {args.export}")


if __name__ == "__main__":
    main()
