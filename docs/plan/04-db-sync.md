# Plan — Database Sync (Parquet → Postgres)

Component: promote the sales-relevant slice of the analytical dataset into the application database.

Source of truth files:
- `sales_intelligence/services/sync.py`
- `sales_intelligence/commands/sync.py`

## Purpose

A one-way, offline operation that copies companies at or above a score threshold from Parquet into PostgreSQL (Supabase), along with their signal rows, so the product layer never reads the full analytical dataset from the database.

## Flow

1. `iter_qualified_companies(dataset_path, *, min_score, batch_size)` walks the dataset with offset pagination via `query_companies` ([`03-analytics-layer.md`](03-analytics-layer.md)), yielding batches. Stops at the first empty/short batch.
2. For each batch, `DatabaseSyncService.sync` upserts rows inside one `session_factory.begin()` transaction:
   - `Company` — domain, organization, country, city, industry, employee_count, `security_score`, `score_version`, `dataset_version`, `is_active=True`. Idempotent by primary key (`session.get` then create/update).
   - `CompanySignal` — asset/surface and exposure counts for the same company.
3. After all batches, `_deactivate_missing` bulk-updates `companies SET is_active=false` for rows of the same `dataset_version` not seen in this run. Older dataset versions are untouched.
4. Tracked end-to-end in `pipeline_runs` (run type `sync`, score version from `DEFAULT_SCORING_CONFIG.score_version`) with audit events `sync_completed` / `sync_failed`.

## CLI

```text
sales-intelligence sync [DATASET]
  --min-score N       (default 60)
  --dataset-version V (default "unknown")
  --batch-size N      (default 1000)
```

`DATASET` defaults to `ANALYTICAL_DATASET`. `DATABASE_URL` is required.

## Validation

- `DATABASE_URL` must be set.
- `0 <= min_score <= 100`, `1 <= batch_size <= 10000` — validated before any database connection.

## Design notes

- **Why not all companies?** The threshold in the score space (`--min-score`) mirrors the product boundary: only sales-relevant exposure enters the app DB, keeping it small and fast. The threshold is configurable per run.
- **Why 10,000+ works:** batching removes the old fixed ceiling.
- **Deactivation is version-scoped:** companies that fell below the threshold for the current dataset version are marked inactive for it without disturbing other versions' rows.
- Raw observations never touch Postgres — only aggregated, scored profiles pass through.

## Integration points

- Read source: [`03-analytics-layer.md`](03-analytics-layer.md)
- Target schema: [`05-database.md`](05-database.md)
- Operations: [`11-deployment.md`](11-deployment.md)