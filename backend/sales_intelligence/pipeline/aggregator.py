"""Observation normalization and incremental company profile aggregation."""

from __future__ import annotations

import re
from typing import Callable, Iterable

from sales_intelligence.pipeline.models import CompanyProfile
from sales_intelligence.scoring import DEFAULT_SCORING_CONFIG, ScoringConfig, score


def normalize_domain(value: object) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"^[a-z]+://", "", value)
    value = value.split("/", 1)[0].split(":", 1)[0]
    return value.removeprefix("www.").strip(".")


def _first(record: dict, *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if value not in (None, "", [], {}):
            return str(value).strip()
    return None


def _domain(record: dict) -> str:
    candidates: list[object] = []
    for key in ("domain", "domains", "hostname", "hostnames", "host"):
        value = record.get(key)
        if isinstance(value, (list, tuple)):
            candidates.extend(value)
        elif value:
            candidates.append(value)
    for candidate in candidates:
        domain = normalize_domain(candidate)
        if domain:
            return domain
    return ""


def _location_value(record: dict, key: str) -> str | None:
    location = record.get("location")
    if isinstance(location, dict):
        value = location.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return _first(record, key)


def _employee_count(record: dict) -> int | None:
    value = _first(record, "employee_count", "employees", "employees_count", "company_size")
    if not value:
        return None
    match = re.search(r"\d[\d,]*", value)
    return int(match.group(0).replace(",", "")) if match else None


def _vulnerabilities(record: dict) -> tuple[set[str], set[str]]:
    raw = record.get("vulns", record.get("vulnerabilities", record.get("cves", [])))
    if isinstance(raw, dict):
        vulnerability_ids = {str(key) for key in raw}
        critical = {
            str(key)
            for key, details in raw.items()
            if isinstance(details, dict)
            and any(
                isinstance(details.get(field), (int, float)) and details[field] >= 9
                for field in ("cvss", "cvss_v2", "cvss_v3")
            )
        }
        return vulnerability_ids, critical
    values = _values({"vulnerabilities": raw}, "vulnerabilities")
    return set(values), {value for value in values if "critical" in value.lower()}


def company_id_for(record: dict) -> str:
    domain = _domain(record)
    organization = (_first(record, "organization", "org", "company") or "").lower()
    return domain or re.sub(r"[^a-z0-9]+", "-", organization).strip("-") or "unknown"


def _values(record: dict, *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        raw = record.get(key, [])
        if isinstance(raw, str):
            raw = [raw]
        if isinstance(raw, (list, tuple, set)):
            values.extend(str(item).strip() for item in raw if str(item).strip())
    return values


def _contains(values: Iterable[str], *needles: str) -> bool:
    text = " ".join(values).lower()
    return any(needle in text for needle in needles)


class CompaniesAggregator:
    """Folds observation records into company profiles and scores them.

    Usage::

        aggregator = CompaniesAggregator(initial_profiles=resume_profiles)
        for record in RecordSource("observations.jsonl"):
            aggregator.consume(record)
        profiles = aggregator.finalize()
    """

    def __init__(
        self,
        *,
        scoring_config: ScoringConfig = DEFAULT_SCORING_CONFIG,
        initial_profiles: Iterable[CompanyProfile] | None = None,
    ):
        self.scoring_config = scoring_config
        self.companies: dict[str, CompanyProfile] = {
            profile.company_id: profile for profile in (initial_profiles or [])
        }

    @property
    def count(self) -> int:
        return len(self.companies)

    def consume(self, record: dict) -> str:
        """Fold a single observation record into the matching profile and return its company id."""
        company_id = company_id_for(record)
        domain = _domain(record)
        company = self.companies.setdefault(
            company_id, CompanyProfile(company_id=company_id, domain=domain)
        )
        company.asset_count += 1
        company.organization = company.organization or _first(record, "organization", "org", "company")
        company.country = company.country or _location_value(record, "country_code") or _location_value(record, "country")
        company.city = company.city or _location_value(record, "city")
        company.industry = company.industry or _first(record, "industry", "sector")
        company.employee_count = company.employee_count or _employee_count(record)

        ip = _first(record, "ip_str", "ip", "ip_address")
        if ip:
            company._ips.add(ip)
        for candidate in record.get("domains", []) if isinstance(record.get("domains"), list) else [domain]:
            normalized = normalize_domain(candidate)
            if normalized:
                company._domains.add(normalized)

        vulnerabilities, critical_vulnerabilities = _vulnerabilities(record)
        company._vulnerabilities.update(vulnerabilities)
        company._critical_vulnerabilities.update(critical_vulnerabilities)
        tags = _values(record, "tags", "tag")
        products = _values(record, "product", "products", "service")
        combined = tags + products + _values(record, "port", "ports") + list(record.keys())
        company._eol_products.update(value for value in tags if "eol" in value.lower())
        company._eol_products.update(_values(record, "eol_products", "eol", "end_of_life"))
        company.exposed_rdp = company.exposed_rdp or _contains(combined, "rdp", "3389") or "rdp_encryption" in record
        company.exposed_database = company.exposed_database or _contains(combined, "mysql", "postgres", "mongodb", "redis", "database", "3306", "5432")
        company.exposed_exchange = company.exposed_exchange or _contains(combined, "exchange") or "microsoft_exchange" in record
        company.security_tag_count += sum("security" in tag.lower() or "cve" in tag.lower() for tag in tags)
        return company_id

    def finalize(self) -> list[CompanyProfile]:
        """Populate counts, apply scoring, and return profiles sorted by descending score."""
        for company in self.companies.values():
            company.unique_ip_count = len(company._ips)
            company.unique_domain_count = len(company._domains)
            company.vulnerability_count = len(company._vulnerabilities)
            company.critical_vulnerability_count = len(company._critical_vulnerabilities)
            company.eol_product_count = len(company._eol_products)
            company.score_version = self.scoring_config.score_version
            company.security_score = score(company, self.scoring_config)
        return sorted(
            self.companies.values(),
            key=lambda item: (-item.security_score, item.company_id),
        )

    def run(
        self,
        records: Iterable[dict],
        *,
        on_record: Callable[[int, dict[str, CompanyProfile]], None] | None = None,
    ) -> list[CompanyProfile]:
        """Consume all records and return the finalized, scored profiles."""
        processed = 0
        for record in records:
            self.consume(record)
            processed += 1
            if on_record:
                on_record(processed, self.companies)
        return self.finalize()