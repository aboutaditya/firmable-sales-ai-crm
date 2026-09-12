from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class EvaluationCase:
    company_id: str
    expected_priority: str
    expected_score: int


@dataclass(frozen=True)
class Prediction:
    company_id: str
    priority: str
    ai_score: int


def load_cases(path: str | Path) -> list[EvaluationCase]:
    cases = []
    for row in _load_rows(path):
        cases.append(
            EvaluationCase(
                company_id=row["company_id"],
                expected_priority=row["expected_priority"],
                expected_score=int(row["expected_score"]),
            )
        )
    return cases


def load_predictions(path: str | Path) -> list[Prediction]:
    predictions = []
    for row in _load_rows(path):
        predictions.append(
            Prediction(
                company_id=row["company_id"],
                priority=row["priority"],
                ai_score=int(row["ai_score"]),
            )
        )
    return predictions


def evaluate(
    cases: Iterable[EvaluationCase],
    predictions: Iterable[Prediction],
    *,
    prompt_version: str = "unknown",
) -> dict:
    expected = {case.company_id: case for case in cases}
    actual = {prediction.company_id: prediction for prediction in predictions}
    missing = sorted(set(expected) - set(actual))
    if missing:
        raise ValueError(f"Missing predictions for: {', '.join(missing)}")

    matched = [actual[company_id] for company_id in expected]
    expected_priorities = [expected[p.company_id].expected_priority for p in matched]
    predicted_priorities = [p.priority for p in matched]
    tp = sum(e == "HIGH" and p == "HIGH" for e, p in zip(expected_priorities, predicted_priorities))
    fp = sum(e != "HIGH" and p == "HIGH" for e, p in zip(expected_priorities, predicted_priorities))
    fn = sum(e == "HIGH" and p != "HIGH" for e, p in zip(expected_priorities, predicted_priorities))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    mae = sum(abs(expected[p.company_id].expected_score - p.ai_score) for p in matched) / len(matched)
    return {
        "prompt_version": prompt_version,
        "examples": len(matched),
        "priority_accuracy": sum(e == p for e, p in zip(expected_priorities, predicted_priorities)) / len(matched),
        "high_priority_precision": precision,
        "high_priority_recall": recall,
        "high_priority_f1": f1,
        "score_mae": mae,
    }


def compare_results(current: dict, previous: dict) -> dict:
    """Return metric deltas with the current prompt as the numerator."""
    metric_names = (
        "priority_accuracy",
        "high_priority_precision",
        "high_priority_recall",
        "high_priority_f1",
        "score_mae",
    )
    return {
        metric: round(current[metric] - previous[metric], 6)
        for metric in metric_names
    }


def _load_rows(path: str | Path) -> list[dict]:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Prediction file not found: {path}. Create one JSON object per line "
            "with company_id, priority, and ai_score, or use evals/results/predictions.jsonl."
        )
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate saved account-scoring predictions")
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--prompt-version", default="unknown")
    parser.add_argument(
        "--previous-predictions",
        type=Path,
        help="Optional predictions file for the prompt version being replaced",
    )
    parser.add_argument(
        "--previous-prompt-version",
        default="previous",
        help="Label for the previous prompt version in the report",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        load_cases(args.cases),
        load_predictions(args.predictions),
        prompt_version=args.prompt_version,
    )
    if args.previous_predictions:
        previous = evaluate(
            load_cases(args.cases),
            load_predictions(args.previous_predictions),
            prompt_version=args.previous_prompt_version,
        )
        result["previous"] = previous
        result["comparison"] = compare_results(result, previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
