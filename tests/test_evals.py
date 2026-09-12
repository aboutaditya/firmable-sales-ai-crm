import unittest

from evals.harness import EvaluationCase, Prediction, compare_results, evaluate


class EvaluationTests(unittest.TestCase):
    def test_calculates_priority_metrics_and_score_error(self):
        result = evaluate(
            [
                EvaluationCase("high", "HIGH", 90),
                EvaluationCase("low", "LOW", 20),
            ],
            [
                Prediction("high", "HIGH", 80),
                Prediction("low", "HIGH", 30),
            ],
            prompt_version="v1",
        )
        self.assertEqual(result["examples"], 2)
        self.assertEqual(result["priority_accuracy"], 0.5)
        self.assertEqual(result["high_priority_precision"], 0.5)
        self.assertEqual(result["high_priority_recall"], 1.0)
        self.assertEqual(result["score_mae"], 10.0)

    def test_rejects_missing_predictions(self):
        with self.assertRaises(ValueError):
            evaluate(
                [EvaluationCase("missing", "LOW", 10)],
                [],
            )

    def test_compares_current_metrics_to_previous_version(self):
        previous = {"priority_accuracy": 0.5, "high_priority_precision": 0.5, "high_priority_recall": 0.5, "high_priority_f1": 0.5, "score_mae": 10.0}
        current = {"priority_accuracy": 0.75, "high_priority_precision": 0.75, "high_priority_recall": 0.5, "high_priority_f1": 0.6, "score_mae": 7.0}
        self.assertEqual(
            compare_results(current, previous),
            {
                "priority_accuracy": 0.25,
                "high_priority_precision": 0.25,
                "high_priority_recall": 0.0,
                "high_priority_f1": 0.1,
                "score_mae": -3.0,
            },
        )
