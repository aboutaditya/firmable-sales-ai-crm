import tempfile
import unittest
from pathlib import Path

import jwt
from fastapi.testclient import TestClient

from sales_intelligence.backend.config import Settings
from sales_intelligence.backend.main import create_app
from sales_intelligence.backend.repositories import PostgresCompanyRepository
from sales_intelligence.pipeline import aggregate, iter_records, write_profiles


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.dataset = write_profiles(
            aggregate(iter_records("data/sample/observations.jsonl")),
            Path(cls.directory.name) / "companies.parquet",
            format="parquet",
        )
        cls.client = TestClient(
            create_app(Settings(analytical_dataset=cls.dataset))
        )

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_health(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertTrue(response.headers.get("x-request-id"))

    def test_readiness_uses_analytical_dataset(self):
        response = self.client.get("/api/v1/health/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ready")

    def test_validation_errors_are_structured(self):
        response = self.client.get("/api/v1/companies?limit=0")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"], "VALIDATION_ERROR")
        self.assertTrue(response.json()["request_id"])

    def test_company_list_and_detail(self):
        response = self.client.get("/api/v1/companies?country=US&limit=10")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["company_id"], "acme.com")

        response = self.client.get("/api/v1/companies/acme.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["security_score"], 75)

    def test_missing_company(self):
        response = self.client.get("/api/v1/companies/missing.example")
        self.assertEqual(response.status_code, 404)

    def test_assessment_requires_ai_configuration(self):
        response = self.client.post("/api/v1/companies/acme.com/assess")
        self.assertEqual(response.status_code, 503)

    def test_content_generation_requires_ai_configuration(self):
        self.assertEqual(
            self.client.post("/api/v1/companies/acme.com/summary").status_code,
            503,
        )
        self.assertEqual(
            self.client.post("/api/v1/companies/acme.com/outreach").status_code,
            503,
        )

    def test_queue_requires_an_authenticated_user(self):
        self.assertEqual(self.client.get("/api/v1/me/preferences").status_code, 401)
        self.assertEqual(self.client.get("/api/v1/me/queue/next").status_code, 401)

    def test_authentication_protects_business_routes_when_enabled(self):
        app = create_app(
            Settings(
                analytical_dataset=self.dataset,
                auth_required=True,
                supabase_jwt_secret="test-secret",
            )
        )
        client = TestClient(app)
        self.assertEqual(client.get("/api/v1/companies").status_code, 401)
        token = jwt.encode(
            {"sub": "user-1", "aud": "authenticated", "role": "authenticated", "roles": ["sales_rep"]},
            "test-secret",
            algorithm="HS256",
        )
        response = client.get(
            "/api/v1/companies",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            client.get(
                "/api/v1/admin/users",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code,
            403,
        )
        self.assertEqual(
            client.patch(
                "/api/v1/me/preferences",
                json={"min_exposure_score": 80},
                headers={"Authorization": f"Bearer {token}"},
            ).status_code,
            403,
        )
        self.assertEqual(
            client.patch(
                "/api/v1/users/user-2/queue-preferences",
                json={"min_exposure_score": 80},
                headers={"Authorization": f"Bearer {token}"},
            ).status_code,
            403,
        )

    def test_database_configuration_selects_postgres_repository(self):
        app = create_app(Settings(database_url="postgresql://example.invalid/db"))
        self.assertIsInstance(app.state.company_service.repository, PostgresCompanyRepository)
