# Plan — ETL / Ingestion Pipeline

Component: streaming ingestion, normalization, and aggregation of raw observations into company-level analytical data.

Source of truth files:
- `sales_intelligence/pipeline.py`
- `sales_intelligence/services/pipeline/service.py`
- `sales_intelligence/services/pipeline/manifest.py`
- `sales_intelligence/services/pipeline/checkpoint.py`
- `sales_intelligence/services/pipeline/files.py`
- `sales_intelligence/commands/etl.py`

## Purpose

Convert a large, observation-oriented dataset (JSONL, optionally `.gz`/`.zst`, local or HTTP) into compact company profiles without ever loading the raw dataset into memory. This is the **only** place raw observations are read.

## Input contract

`iter_records(source)` streams JSON Lines, one JSON object per record. Supported sources:

- Local file paths.
- `http`/`https` URLs (compression detected from `content-type` or the B2 `x-bz-file-name` header).

Malformed lines raise `ValueError("Invalid JSON on line N")` / `ValueError("Expected an object on line N")`.

Fields are extracted from the Shodan-shaped source schema with tolerant normalization:

- Domain / company id — via `normalize_domain` (strips scheme, path, port, `www.`), `company_id_for` (domain → slugified org → `"unknown"`).
- Location — prefers a `location` dict over top-level `country_code`/`country`/`city`.
- Employees — first integer found among `employee_count`/`employees`/`employees_count`/`company_size`.
- Vulnerabilities — from `vulns`/`vulnerabilities`/`cves`, with critical flagged when CVSS >= 9 or the label contains "critical".
- Exposure booleans — `exposed_rdp`, `exposed_database`, `exposed_exchange` derived from tags, products, ports, and record keys.

## Aggregation

`aggregate(records)` groups records by `company_id` into `CompanyProfile` objects:

- `asset_count` increments per record; IPs/domains/vulns/critical vulns/EOL products accumulate into de-duplicated sets.
- Organization, country, city, industry, employee count are filled on first non-empty value.
- Counts are derived from set lengths after aggregation; `security_score` is computed by the scoring engine ([`02-scoring.md`](02-scoring.md)).
- Profiles sort by `(-security_score, company_id)` for deterministic output.

`CompanyProfile` retains only public fields in `to_dict()`; internal sets are excluded.

## Output

`write_profiles(profiles, output, format)` supports `jsonl` (default fallback) and `parquet` (requires the optional `pyarrow`/`.[analytics]` extras). Output defaults to `data/processed/companies.parquet`.

## Checkpointing and resume

The service is resumable. State is stored in a checkpoint file (`CheckpointStore`, default written alongside the output):

- Checkpoints save at `--checkpoint-interval` records (default 10,000) with running state + serialized profiles.
- Resume is allowed only when the source checksum, `dataset_version`, and effective `score_version` match; a `completed` checkpoint can be extended by requesting a larger `max_records`. A checkpoint recorded under a different score version aborts with an error so results stay reproducible.
- Writes are atomic (`.tmp` then `os.replace`).

## Scoring configuration

Deterministic scoring weighs/tiers come from a `ScoringConfig` ([`02-scoring.md`](02-scoring.md)). The ETL `--scoring-config PATH` flag loads a JSON override file; otherwise `SCORING_CONFIG_PATH` (env) or the built-in defaults apply. The effective score version is recorded in every checkpoint, manifest, and database run row.

## Manifests and dataset control plane

Each run produces:

- A sidecar manifest next to the output (`<output>.manifest.json`): run id, dataset version, score version, source, source checksum, format, processed count, company count.
- A run manifest under `--dataset-runs-dir` (default `<output>/../dataset_runs/`): `<run_id>.json` plus a `current.json` pointer.

When `DATABASE_URL` is set, ETL also records `dataset_runs` and `pipeline_runs` rows and writes progress; failures are recorded before re-raising. The database `dataset_runs` row (with `is_current`) is the canonical control-plane record; local JSON is a diagnostic fallback.

## CLI

```text
sales-intelligence etl [SOURCE]
  --output PATH            (default data/processed/companies.parquet)
  --format {jsonl,parquet} (default parquet)
  --max-records N
  --dataset-version V      (defaults to the source checksum)
  --scoring-config PATH    (optional JSON override of ScoringConfig)
  --checkpoint PATH
  --checkpoint-interval N  (default 10000)
  --dataset-runs-dir DIR
  --dataset-name NAME      (default "companies")
```

`SOURCE` defaults to `RAW_DATASET_URL`.

## Integration points

- Scoring: [`02-scoring.md`](02-scoring.md)
- Analytical reads: [`03-analytics-layer.md`](03-analytics-layer.md)
- Database tracking: [`05-database.md`](05-database.md)
- Operations (Makefile `make etl`): [`11-deployment.md`](11-deployment.md)