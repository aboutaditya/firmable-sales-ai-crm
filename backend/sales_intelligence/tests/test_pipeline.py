import json
import tempfile
import unittest
from pathlib import Path

from sales_intelligence.pipeline import aggregate, company_id_for, iter_records, normalize_domain, write_profiles
from sales_intelligence.query import query_companies
from sales_intelligence.services.sync import DatabaseSyncService
from sales_intelligence.services.sync import iter_qualified_companies


class PipelineTests(unittest.TestCase):
    def test_normalizes_domain_and_company_id(self):
        self.assertEqual(normalize_domain("https://WWW.Acme.com:443/path"), "acme.com")
        self.assertEqual(company_id_for({"hostname": "www.Acme.com"}), "acme.com")

    def test_aggregates_signals_and_score(self):
        profiles = aggregate(iter_records("data/sample/observations.jsonl"))
        acme = next(profile for profile in profiles if profile.company_id == "acme.com")
        self.assertEqual(acme.asset_count, 2)
        self.assertEqual(acme.unique_ip_count, 2)
        self.assertEqual(acme.vulnerability_count, 2)
        self.assertEqual(acme.critical_vulnerability_count, 1)
        self.assertTrue(acme.exposed_rdp)
        self.assertTrue(acme.exposed_database)
        self.assertEqual(acme.security_score, 75)

    def test_jsonl_export_is_reproducible(self):
        profiles = aggregate(iter_records("data/sample/observations.jsonl"))
        with tempfile.TemporaryDirectory() as directory:
            output = write_profiles(profiles, Path(directory) / "companies.jsonl")
            rows = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual([row["company_id"] for row in rows], ["acme.com", "example.org"])

    def test_shodan_shape_is_normalized(self):
        profiles = aggregate(
            [
                {
                    "domains": ["www.example.com"],
                    "hostnames": ["host.example.com"],
                    "org": "Example Org",
                    "ip_str": "203.0.113.5",
                    "location": {"country_code": "US", "city": "Austin"},
                    "port": 3389,
                    "tags": ["eol-product"],
                    "rdp_encryption": {"levels": []},
                    "vulns": {"CVE-2026-0001": {"cvss": 9.8}},
                }
            ]
        )
        profile = profiles[0]
        self.assertEqual(profile.company_id, "example.com")
        self.assertEqual(profile.organization, "Example Org")
        self.assertEqual(profile.country, "US")
        self.assertEqual(profile.city, "Austin")
        self.assertEqual(profile.vulnerability_count, 1)
        self.assertEqual(profile.critical_vulnerability_count, 1)
        self.assertEqual(profile.eol_product_count, 1)
        self.assertTrue(profile.exposed_rdp)

    def test_query_validates_pagination_before_optional_dependency(self):
        with self.assertRaises(ValueError):
            query_companies("missing.parquet", limit=0)
        with self.assertRaises(ValueError):
            query_companies("missing.parquet", offset=-1)

    def test_sync_validates_configuration_before_database_connection(self):
        service = DatabaseSyncService()
        with self.assertRaises(ValueError):
            service.sync("missing.parquet", "", min_score=60)
        with self.assertRaises(ValueError):
            service.sync("missing.parquet", "postgresql://unused", min_score=101)
        with self.assertRaises(ValueError):
            service.sync("missing.parquet", "postgresql://unused", batch_size=0)

    def test_qualified_rows_are_read_in_batches(self):
        profiles = aggregate(iter_records("data/sample/observations.jsonl"))
        with tempfile.TemporaryDirectory() as directory:
            dataset = write_profiles(
                profiles, Path(directory) / "companies.parquet", format="parquet"
            )
            batches = list(
                iter_qualified_companies(dataset, min_score=0, batch_size=1)
            )
        self.assertEqual([len(batch) for batch in batches], [1, 1])


if __name__ == "__main__":
    unittest.main()
