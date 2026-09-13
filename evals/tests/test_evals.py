import unittest

from evals.harness import EvaluationCase, Prediction, compare_results, evaluate
from evals.harness_output import evaluate_content, fetch_storage_trace_rows, load_trace_rows, run_golden, run_traces


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


class OutputRubricTests(unittest.TestCase):
    def test_negated_signal_is_not_invented(self):
        criteria, _ = evaluate_content(
            "company_summary",
            "Although no critical vulnerabilities or exposed databases were detected, RDP is exposed.",
            {"critical_vulnerability_count": 0, "exposed_database": False, "exposed_rdp": True},
        )
        self.assertTrue(criteria["no_invented_signal"])
        self.assertTrue(criteria["covers_signal"])

    def test_assertive_breach_claim_fails_fabrication(self):
        criteria, _ = evaluate_content(
            "outreach",
            "We detected a breach in your network. Would you like to book a call?",
            {"vulnerability_count": 1, "exposed_rdp": True},
        )
        self.assertFalse(criteria["no_fabrication"])

    def test_negated_breach_mention_passes_fabrication(self):
        criteria, _ = evaluate_content(
            "outreach",
            "This is not evidence of a breach, but validation is worth doing. Want a call?",
            {"vulnerability_count": 1, "exposed_rdp": True},
        )
        self.assertTrue(criteria["no_fabrication"])

    def test_unicode_dash_matches_eol_term(self):
        criteria, _ = evaluate_content(
            "company_summary",
            "It runs an end\u2011of\u2011life product.",
            {"eol_product_count": 1},
        )
        self.assertTrue(criteria["covers_signal"])

    def test_short_token_uses_word_boundaries(self):
        criteria, _ = evaluate_content(
            "outreach",
            "Theology coursework aside, is your RDP reachable?",
            {"eol_product_count": 0, "exposed_rdp": True, "vulnerability_count": 0},
        )
        self.assertTrue(criteria["no_invented_signal"])  # "theology" must not match "eol"
        self.assertTrue(criteria["covers_signal"])

    def test_covers_signal_is_none_when_profile_has_no_signals(self):
        criteria, notes = evaluate_content(
            "outreach",
            "Hello, want to chat?",
            {"vulnerability_count": 0, "exposed_rdp": False, "eol_product_count": 0},
        )
        self.assertIsNone(criteria["covers_signal"])

    def test_golden_run_reports_clean_pass_accuracy(self):
        import json
        import tempfile
        from pathlib import Path

        rows = [
            {"company_id": "a", "feature": "outreach", "content": "Subject: X\n\nRDP is exposed. Want a call?",
             "company": {"exposed_rdp": True}, "expected": {"covers_signal": True, "no_fabrication": True}},
            {"company_id": "b", "feature": "outreach", "content": "Subject: X\n\nWe detected a breach. Want a call?",
             "company": {"exposed_rdp": True, "vulnerability_count": 1}, "expected": {"covers_signal": True, "no_fabrication": False}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            from evals import harness_output

            result = harness_output.run_golden([json.loads(line) for line in path.read_text().splitlines()])
        self.assertEqual(result["clean_pass_accuracy"], 1.0)
        self.assertEqual(result["per_criterion"]["no_fabrication"]["recall"], 1.0)

    def test_trace_run_skips_error_rows(self):
        import json
        import tempfile
        from pathlib import Path

        rows = [
            {"trace_id": "ok", "status": "success", "feature": "outreach", "prompt_version": "outreach-v1",
             "request": {"company": {"exposed_rdp": True}},
             "response": {"content": "Subject: X\n\nYour RDP is exposed. Want a call?"}},
            {"trace_id": "err", "status": "error", "feature": "outreach", "error": "boom"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "traces.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            result = run_traces(load_trace_rows(path))
        self.assertEqual(result["traces_total"], 2)
        self.assertEqual(result["traces_success"], 1)
        self.assertEqual(result["content_rows_evaluated"], 1)
        self.assertEqual(result["by_feature"]["outreach"]["clean_pass_rate"], 1.0)

    def test_storage_fetch_reassembles_jsonl_records(self):
        import json
        from unittest import mock

        list_response = [{"name": "traces/outreach/2026/09/13/t1.json"}, {"name": "traces/outreach/2026/09/13/t2.json"}]
        records = [{"trace_id": "t1", "feature": "outreach"}, {"trace_id": "t2", "feature": "outreach"}]
        side_effects = [bytes(json.dumps(list_response), "utf-8"), bytes(json.dumps(records[0]), "utf-8"), bytes(json.dumps(records[1]), "utf-8")]

        class FakeResponse:
            def __init__(self, body):
                self.body = body
                self.status = 200

            def read(self):
                return self.body

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def urlopen(request, timeout=15.0):
            return FakeResponse(side_effects.pop(0))

        with mock.patch("urllib.request.urlopen", side_effect=urlopen) as mocked:
            rows = fetch_storage_trace_rows("https://proj.supabase.co", "service-key", "llm-traces")
        self.assertEqual(rows, records)
        self.assertEqual(mocked.call_count, 3)
        self.assertIn("traces/outreach/2026/09/13/t1.json", mocked.call_args_list[1].args[0].full_url)
