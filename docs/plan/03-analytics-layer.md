# Plan — Analytical Layer (Parquet + DuckDB)

Component: the analytical read path over the Parquet dataset. Supports ranked, filtered, paginated company queries without any database.

Source of truth files:
- `sales_intelligence/query.py`
- `sales_intelligence/repositories/companies.py::ParquetCompanyRepository`
- `sales_intelligence/services/companies.py::CompanyService`

## Purpose

Serve deterministic reads (filter, rank, paginate) over `companies.parquet` with DuckDB. This is the local/demo read path and the source for the sync command; in production with `DATABASE_URL` configured, the API switches to the Postgres read path with the same filter vocabulary.

## Query function

`query_companies(parquet_path, *, company_id, country, min_score, industry, min_employee_count, signals, limit=100, offset=0, cursor=None)`

Validation: `limit` 1–10,000, `offset >= 0`, `min_employee_count >= 0`, unknown signal → `ValueError`.

### Filters

| Parameter | Semantics |
| --- | --- |
| `company_id` | exact id match |
| `country` | exact country match |
| `min_score` | `security_score >= ?` |
| `industry` | exact industry match |
| `min_employee_count` | `employee_count >= ?` |
| `signals` | allowed: `rdp`, `database`, `exchange`, `vulnerability`, `critical`, `eol` — boolean flags must be `true`, count columns must be `> 0` |

### Pagination

- `limit`/`offset` for simple paging.
- `cursor` for keyset pagination over `(security_score, company_id)`, encoded as urlsafe-base64 JSON. Keeps ranking stable while pages advance.

SQL is parameterized; the resolved file path is escaped by doubling single quotes before quoting.

## Repositories

- `ParquetCompanyRepository(dataset_path)` — `list_companies`/`get_company`, delegating to `query_companies`. Restricts `sales_rep` role (returns `[]` / denies) so reps cannot browse the global list.
- `CompanyService` — orchestrates, builds the `next_cursor` (only when a page is full), and returns the standard dict shape shared with the Postgres repository.

## CLI

```text
sales-intelligence query DATASET
  --company-id ID
  --country CC
  --min-score N
  --limit N    (default 100)
  --offset N   (default 0)
```

Rows print as sorted JSON.

## Design notes

- The filter vocabulary is **identical** to `PostgresCompanyRepository` ([`05-database.md`](05-database.md)), so switching `DATABASE_URL` on/off changes only the backend, not the API contract.
- DuckDB queries Parquet directly (predicate pushdown); no copy of the analytical dataset is kept in Postgres.

## Integration points

- Data source: [`01-etl.md`](01-etl.md)
- Score semantics: [`02-scoring.md`](02-scoring.md)
- Sync reads: [`04-db-sync.md`](04-db-sync.md)
- API exposure: [`06-api.md`](06-api.md)