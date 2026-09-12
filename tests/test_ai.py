import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from sales_intelligence.backend.pydantic import QualificationResult
from sales_intelligence.backend.ai.provider import OpenAICompatibleProvider, TextProviderResponse
from sales_intelligence.backend.ai.provider import LLMProviderError, _provider_error
from sales_intelligence.backend.ai.content_service import AIContentService
from sales_intelligence.backend.ai.service import AIQualificationService
from sales_intelligence.backend.ai.tracing import JsonlTraceSink


class FakeCompanyRepository:
    def get_company(self, company_id, **_):
        return {"company_id": company_id, "security_score": 75}


class FakeAssessmentRepository:
    def __init__(self, cached=None):
        self.cached = cached
        self.saved = None

    def get_latest(self, company_id, prompt_version):
        return self.cached

    def save(self, **kwargs):
        self.saved = SimpleNamespace(
            model=kwargs["model"],
            prompt_version=kwargs["prompt_version"],
            latency_ms=kwargs["latency_ms"],
            cost_usd=None,
            **kwargs["result"],
        )
        return self.saved


class FakeProvider:
    model = "test-model"

    def qualify(self, company, prompt):
        return QualificationResult(
            ai_score=88,
            priority="HIGH",
            confidence=0.9,
            reasoning="Strong observed exposure.",
        )

    def generate(self, company, prompt):
        return TextProviderResponse("Subject: Test\n\nBody: Evidence-led note.", 10, 8, 0.001)


class AiServiceTests(unittest.TestCase):
    def test_provider_error_preserves_actionable_status_and_message(self):
        import httpx

        response = httpx.Response(
            404,
            json={"error": {"message": "No available providers for this model"}},
            request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        )
        error = _provider_error(response)
        self.assertIsInstance(error, LLMProviderError)
        self.assertEqual(error.status_code, 404)
        self.assertIn("No available providers", str(error))

    def test_jsonl_trace_sink_writes_structured_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "traces" / "llm.jsonl"
            trace_id = JsonlTraceSink(path).record(
                feature="account_scoring",
                model="test-model",
                prompt_version="account-scoring-v1",
                request={"company_id": "acme.com"},
                response={"priority": "HIGH"},
                latency_ms=12,
                input_tokens=10,
                output_tokens=5,
                cost_usd=0.001,
                decision="HIGH",
                status="success",
                error=None,
            )
            row = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(row["trace_id"], trace_id)
        self.assertEqual(row["request"]["company_id"], "acme.com")
        self.assertEqual(row["decision"], "HIGH")

    def test_assessment_is_generated_and_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("{{company_profile}}", encoding="utf-8")
            repository = FakeAssessmentRepository()
            service = AIQualificationService(
                FakeCompanyRepository(), repository, FakeProvider(), prompt
            )
            result = service.assess("acme.com")
        self.assertEqual(result.ai_score, 88)
        self.assertFalse(result.cached)
        self.assertIsNotNone(repository.saved)

    def test_cached_assessment_skips_generation(self):
        cached = SimpleNamespace(
            ai_score=71,
            priority="MEDIUM",
            reasoning="Cached result",
            model="test-model",
            prompt_version="account-scoring-v1",
            latency_ms=20,
            cost_usd=None,
        )
        with tempfile.TemporaryDirectory() as directory:
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("prompt", encoding="utf-8")
            result = AIQualificationService(
                FakeCompanyRepository(), FakeAssessmentRepository(cached), FakeProvider(), prompt
            ).assess("acme.com")
        self.assertTrue(result.cached)
        self.assertEqual(result.ai_score, 71)

    def test_corrective_retry_recovers_from_non_json_response(self):
        import httpx
        from unittest import mock

        valid = {
            "ai_score": 60,
            "priority": "MEDIUM",
            "confidence": 0.7,
            "reasoning": "Observed exposure.",
        }
        responses = [
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": "Sure, here are some thoughts..."}}], "usage": {}},
                request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
            ),
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": json.dumps(valid)}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
                request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
            ),
        ]
        provider = OpenAICompatibleProvider(api_key="k", base_url="https://openrouter.ai/api/v1", model="m")
        with mock.patch("httpx.post", side_effect=responses) as post:
            result = provider.qualify({"company_id": "acme.com"}, "{{company_profile}}")
        self.assertEqual(result.result.priority, "MEDIUM")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(result.input_tokens, 10)
        self.assertEqual(result.output_tokens, 5)

    def test_corrective_retry_raises_when_still_invalid(self):
        import httpx
        from unittest import mock

        response = httpx.Response(
            200,
            json={"choices": [{"message": {"content": "still not json"}}], "usage": {}},
            request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions"),
        )
        provider = OpenAICompatibleProvider(api_key="k", base_url="https://openrouter.ai/api/v1", model="m")
        with mock.patch("httpx.post", return_value=response):
            with self.assertRaises(ValueError):
                provider.qualify({"company_id": "acme.com"}, "{{company_profile}}")

    def test_content_is_generated_and_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt_root = Path(directory)
            (prompt_root / "company_summary").mkdir()
            (prompt_root / "company_summary" / "v1.txt").write_text("summary", encoding="utf-8")
            repository = FakeAssessmentRepository()
            service = AIContentService(FakeCompanyRepository(), repository, FakeProvider(), prompt_root)
            # Reuse a small fake repository with the content methods expected by the service.
            repository.get_latest = lambda company_id, feature, prompt_version: None
            repository.save = lambda **values: SimpleNamespace(**values, id=1)
            result = service.generate("acme.com", "company_summary")
        self.assertEqual(result["feature"], "company_summary")
        self.assertFalse(result["cached"])
