import json
import unittest
from datetime import datetime, timezone
from unittest import mock

from sales_intelligence.ai.tracing import JsonlTraceSink


class TraceSinkTests(unittest.TestCase):
    def test_jsonl_sink_appends_rows(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "traces" / "llm.jsonl"
            sink = JsonlTraceSink(path)
            sink.record(feature="outreach", prompt_version="outreach-v1", status="error")
            sink.record(feature="outreach", prompt_version="outreach-v1", status="success")
            lines = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["feature"], "outreach")
        self.assertIn("trace_id", lines[0])



if __name__ == "__main__":
    unittest.main()