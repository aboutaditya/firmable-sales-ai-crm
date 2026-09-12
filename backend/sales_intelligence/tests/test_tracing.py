import json
import unittest
from datetime import datetime, timezone
from unittest import mock

from sales_intelligence.ai.tracing import JsonlTraceSink, SupabaseStorageTraceSink
from sales_intelligence.api.container import build_trace_sink
from sales_intelligence.config import Settings


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

    def test_storage_sink_uploads_one_record_per_object(self):
        calls = []
        now = datetime.now(timezone.utc)

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def urlopen(request, timeout=10.0):
            calls.append(request)
            return FakeResponse()

        with mock.patch("urllib.request.urlopen", side_effect=urlopen), mock.patch(
            "sales_intelligence.ai.tracing.datetime"
        ) as fake_datetime:
            fake_datetime.now.return_value = now
            fake_datetime.timezone = timezone
            sink = SupabaseStorageTraceSink("https://proj.supabase.co", "service-key", "llm-traces")
            sink.record(feature="outreach", prompt_version="outreach-v1", status="success")

        self.assertEqual(len(calls), 1)
        url = calls[0].full_url
        self.assertTrue(url.startswith("https://proj.supabase.co/storage/v1/object/llm-traces/traces/outreach-v1/"))
        self.assertIn(f"/{now:%Y}/{now:%m}/{now:%d}/", url)
        self.assertTrue(url.endswith(".json"))
        self.assertEqual(calls[0].get_header("Authorization"), "Bearer service-key")
        body = json.loads(calls[0].data)
        self.assertEqual(body["feature"], "outreach")
        self.assertEqual(body["status"], "success")

    def test_storage_sink_warns_and_keeps_trace_id_on_failure(self):
        with mock.patch("urllib.request.urlopen", side_effect=RuntimeError("bucket unreachable")):
            sink = SupabaseStorageTraceSink("https://proj.supabase.co", "key", "llm-traces")
            trace_id = sink.record(feature="outreach")
        self.assertTrue(trace_id)

    def test_build_trace_sink_storage_requires_supabase_env(self):
        with self.assertRaises(ValueError):
            build_trace_sink(Settings(llm_trace_backend="storage"))

    def test_build_trace_sink_composes_both_backends(self):
        settings = Settings(
            llm_trace_backend="both",
            supabase_url="https://proj.supabase.co",
            supabase_service_role_key="key",
        )
        sink = build_trace_sink(settings)
        self.assertEqual(len(sink.sinks), 2)


if __name__ == "__main__":
    unittest.main()