import json
import os
import tempfile
import unittest
from pathlib import Path

from sales_intelligence.pipeline import CompanyProfile, aggregate, iter_records
from sales_intelligence.scoring import (
    DEFAULT_SCORING_CONFIG,
    ScoringConfig,
    load_scoring_config,
    score,
)


def _profile(**overrides) -> CompanyProfile:
    fields = dict(
        company_id="example.com",
        domain="example.com",
        vulnerability_count=2,
        critical_vulnerability_count=1,
        exposed_rdp=True,
        exposed_database=True,
        eol_product_count=0,
        security_tag_count=0,
        unique_ip_count=0,
        unique_domain_count=0,
        asset_count=0,
    )
    fields.update(overrides)
    return CompanyProfile(**fields)


class ScoringTests(unittest.TestCase):
    def test_default_score_matches_v1_model(self):
        # critical(1) +20, vulnerabilities(2 >= 2) +10, rdp +15, database +15
        self.assertEqual(score(_profile()), 60)

    def test_ip_threshold_controls_points(self):
        self.assertEqual(score(_profile(unique_ip_count=24)), 60)
        self.assertEqual(score(_profile(unique_ip_count=25)), 70)

    def test_exchange_points_are_opt_in(self):
        profile = _profile(exposed_exchange=True)
        self.assertEqual(score(profile), 60)
        config = ScoringConfig(exposed_exchange_points=10)
        self.assertEqual(score(profile, config), 70)

    def test_vulnerability_points_require_threshold(self):
        self.assertEqual(score(_profile(vulnerability_count=1)), 50)
        self.assertEqual(score(_profile(vulnerability_count=2)), 60)

    def test_total_is_capped_at_max_score(self):
        profile = _profile(
            vulnerability_count=10,
            critical_vulnerability_count=10,
            eol_product_count=5,
            security_tag_count=5,
            unique_ip_count=1000,
            exposed_exchange=True,
        )
        self.assertEqual(score(profile), 20 + 10 + 15 + 15 + 10 + 10 + 5)
        self.assertEqual(score(profile, ScoringConfig(max_score=50)), 50)

    def test_json_config_overrides_single_weight(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scoring.json"
            path.write_text(json.dumps({"exposed_rdp_points": 5}))
            config = load_scoring_config(path)
        self.assertIsInstance(config, ScoringConfig)
        self.assertEqual(config.exposed_rdp_points, 5)
        self.assertEqual(config.exposed_database_points, 15)
        self.assertEqual(score(_profile(), config), 50)

    def test_unknown_config_field_raises(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scoring.json"
            path.write_text(json.dumps({"exposed_rds_points": 99}))
            with self.assertRaises(ValueError):
                load_scoring_config(path)

    def test_config_from_environment_variable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scoring.json"
            path.write_text(json.dumps({"critical_vulnerability_points": 40}))
            os.environ["SCORING_CONFIG_PATH"] = str(path)
            try:
                config = load_scoring_config()
            finally:
                del os.environ["SCORING_CONFIG_PATH"]
        self.assertEqual(config.critical_vulnerability_points, 40)
        self.assertEqual(score(_profile(), config), 80)

    def test_load_scoring_config_without_path_returns_defaults(self):
        self.assertIs(load_scoring_config(), DEFAULT_SCORING_CONFIG)

    def test_aggregate_uses_custom_config_and_stamps_score_version(self):
        config = ScoringConfig(score_version="v2-custom", max_score=100)
        profiles = aggregate(
            iter_records("data/sample/observations.jsonl"), scoring_config=config
        )
        acme = next(profile for profile in profiles if profile.company_id == "acme.com")
        self.assertEqual(acme.score_version, "v2-custom")
        self.assertEqual(acme.security_score, 75)


if __name__ == "__main__":
    unittest.main()