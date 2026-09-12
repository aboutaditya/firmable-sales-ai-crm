from __future__ import annotations

import gzip
import hashlib
import json
import re
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator, TextIO
from urllib.parse import urlparse


SCORE_VERSION = "v1"


@dataclass
class CompanyProfile:
    company_id: str
    domain: str
    organization: str | None = None
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    employee_count: int | None = None
    asset_count: int = 0
    unique_ip_count: int = 0
    unique_domain_count: int = 0
    vulnerability_count: int = 0
    critical_vulnerability_count: int = 0
    eol_product_count: int = 0
    exposed_rdp: bool = False
    exposed_database: bool = False
    exposed_exchange: bool = False
    security_tag_count: int = 0
    security_score: int = 0
    score_version: str = SCORE_VERSION
    _ips: set[str] = field(default_factory=set, repr=False)
    _domains: set[str] = field(default_factory=set, repr=False)
    _vulnerabilities: set[str] = field(default_factory=set, repr=False)
    _critical_vulnerabilities: set[str] = field(default_factory=set, repr=False)
    _eol_products: set[str] = field(default_factory=set, repr=False)

    def to_dict(self) -> dict:
        result = asdict(self)
        for internal in ("_ips", "_domains", "_vulnerabilities", "_critical_vulnerabilities", "_eol_products"):
            result.pop(internal, None)
        return result


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


def iter_records(source: str | Path) -> Iterator[dict]:
    """Stream JSONL records from a local file or HTTP(S) object URL."""
    source_text = str(source)
    parsed = urlparse(source_text)
    is_url = parsed.scheme in {"http", "https"}
    source_name = parsed.path if is_url else source_text
    suffix = Path(source_name).suffix.lower()

    if is_url:
        response = urllib.request.urlopen(source_text, timeout=120)
        stream: TextIO | None = None
        try:
            remote_name = response.headers.get("x-bz-file-name", "")
            content_type = response.headers.get("content-type", "").lower()
            if remote_name.endswith(".zst") or "zstd" in content_type:
                suffix = ".zst"
            elif remote_name.endswith(".gz") or "gzip" in content_type:
                suffix = ".gz"
            binary_stream = response
            if suffix == ".zst":
                try:
                    import zstandard
                except ImportError as exc:
                    raise RuntimeError("Reading .zst files requires: pip install zstandard") from exc
                binary_stream = zstandard.ZstdDecompressor().stream_reader(response)
            elif suffix == ".gz":
                binary_stream = gzip.GzipFile(fileobj=response)
            import io

            stream = io.TextIOWrapper(binary_stream)
            yield from _iter_json_lines(stream)
        finally:
            if stream is not None:
                stream.close()
            response.close()
        return

    path = Path(source_text)
    opener = gzip.open if suffix == ".gz" else open
    if suffix == ".zst":
        try:
            import zstandard
        except ImportError as exc:
            raise RuntimeError("Reading .zst files requires: pip install zstandard") from exc
        with path.open("rb") as raw:
            with zstandard.ZstdDecompressor().stream_reader(raw) as decompressed:
                import io

                stream = io.TextIOWrapper(decompressed)
                yield from _iter_json_lines(stream)
        return
    with opener(path, "rt", encoding="utf-8") as stream:
        yield from _iter_json_lines(stream)


def _iter_json_lines(stream: TextIO) -> Iterator[dict]:
    for line_number, line in enumerate(stream, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Expected an object on line {line_number}")
        yield record


def aggregate(
    records: Iterable[dict],
    *,
    initial_profiles: Iterable[CompanyProfile] | None = None,
    on_record: Callable[[int, dict[str, CompanyProfile]], None] | None = None,
) -> list[CompanyProfile]:
    companies: dict[str, CompanyProfile] = {
        profile.company_id: profile for profile in (initial_profiles or [])
    }
    processed = 0
    for record in records:
        company_id = company_id_for(record)
        domain = _domain(record)
        company = companies.setdefault(company_id, CompanyProfile(company_id=company_id, domain=domain))
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
        processed += 1
        if on_record:
            on_record(processed, companies)

    for company in companies.values():
        company.unique_ip_count = len(company._ips)
        company.unique_domain_count = len(company._domains)
        company.vulnerability_count = len(company._vulnerabilities)
        company.critical_vulnerability_count = len(company._critical_vulnerabilities)
        company.eol_product_count = len(company._eol_products)
        company.security_score = score(company)
    return sorted(companies.values(), key=lambda item: (-item.security_score, item.company_id))


def profile_to_state(profile: CompanyProfile) -> dict:
    state = profile.to_dict()
    state.update({
        "_ips": sorted(profile._ips),
        "_domains": sorted(profile._domains),
        "_vulnerabilities": sorted(profile._vulnerabilities),
        "_critical_vulnerabilities": sorted(profile._critical_vulnerabilities),
        "_eol_products": sorted(profile._eol_products),
    })
    return state


def profile_from_state(state: dict) -> CompanyProfile:
    state = dict(state)
    private_sets = {key: set(state.pop(key, [])) for key in ("_ips", "_domains", "_vulnerabilities", "_critical_vulnerabilities", "_eol_products")}
    profile = CompanyProfile(**{key: value for key, value in state.items() if key in CompanyProfile.__dataclass_fields__ and not key.startswith("_")})
    for key, value in private_sets.items():
        setattr(profile, key, value)
    return profile


def score(company: CompanyProfile) -> int:
    points = 0
    points += 20 if company.critical_vulnerability_count else 0
    points += 10 if company.vulnerability_count > 1 else 0
    points += 15 if company.exposed_rdp else 0
    points += 15 if company.exposed_database else 0
    points += 10 if company.eol_product_count else 0
    points += 10 if company.unique_ip_count >= 25 else 0
    points += 5 if company.security_tag_count else 0
    return min(points, 100)


def write_profiles(profiles: Iterable[CompanyProfile], output: str | Path, format: str = "jsonl") -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    profiles = list(profiles)
    if format == "parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise RuntimeError("Parquet output requires: pip install -e '.[analytics]'") from exc
        table = pa.Table.from_pylist([profile.to_dict() for profile in profiles])
        pq.write_table(table, output)
    elif format == "jsonl":
        with output.open("w", encoding="utf-8") as stream:
            for profile in profiles:
                stream.write(json.dumps(profile.to_dict(), sort_keys=True) + "\n")
    else:
        raise ValueError("format must be 'jsonl' or 'parquet'")
    return output


def source_checksum(source: str | Path) -> str:
    """Return a reproducible checksum for a local source, or its URL identity."""
    source_text = str(source)
    parsed = urlparse(source_text)
    digest = hashlib.sha256()
    if parsed.scheme in {"http", "https"}:
        digest.update(source_text.encode("utf-8"))
        return digest.hexdigest()
    with Path(source_text).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
