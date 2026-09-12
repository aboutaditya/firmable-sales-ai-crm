# Operations

Run migrations before starting the API:

```sh
DATABASE_URL="…" ./scripts/apply_migrations.sh
sales-intelligence etl data/demo/observations.jsonl --output data/processed/demo-companies.parquet --dataset-version demo-v1
sales-intelligence sync data/processed/demo-companies.parquet --min-score 60 --dataset-version demo-v1
```

Alembic uses SQLAlchemy's `Base.metadata` as its autogeneration target. After ORM
changes, create a migration with `alembic revision --autogenerate -m "describe change"`.
Existing databases created with the legacy SQL files should be marked with
`alembic stamp 0001_initial_schema` once their schema matches the current models.

ETL writes a sidecar manifest (`.manifest.json`) containing the source identity,
checksum-derived dataset version, record counts, score version, and output format.
With `DATABASE_URL`, ETL and sync create and update `pipeline_runs`; failures are
recorded before being re-raised. `LOG_LEVEL` controls JSON logs.

ETL checkpointing is enabled by the Makefile at
`data/processed/companies.parquet.checkpoint.json`. If a run fails after a
checkpoint, rerun with the same source, dataset version, output, and checkpoint;
the pipeline restores the partial company state and resumes from the last saved
observation. A completed checkpoint is ignored when intentionally starting a new
run. Use `--checkpoint-interval` to tune the checkpoint frequency.

The active dataset pointer is written to
`data/processed/dataset_runs/current.json`. It records the active run manifest,
source URL, dataset version, checkpoint, processed row count, and `next_record`.
Individual run manifests are stored in the same directory using their run IDs as
filenames. The source URL comes from `RAW_DATASET_URL`; `RAW_SOURCE` can still be
passed on the command line for an explicit override.

When `DATABASE_URL` is configured, the canonical version of this pointer is the
`dataset_runs` table. Inspect it with:

```sql
select run_id, dataset_version, source_url, status, processed_rows,
       current_record, next_record, checkpoint_uri, output_uri, is_current
from dataset_runs
where dataset_name = 'companies'
order by updated_at desc;
```

Production workers should resume from the current database row and write checkpoint
and dataset artifacts to object storage. Local JSON files are only a fallback for
development or diagnostics.

For production, schedule ETL followed by sync in the platform scheduler and alert
on a failed `pipeline_runs` row. Store Parquet and manifests in object storage with
versioned retention; database backups and retention are platform responsibilities.

OpenRouter evaluation is independent of PostgreSQL and Supabase. Set
`OPENROUTER_API_KEY` and `OPENROUTER_MODEL`, then run `make eval-openrouter` followed
by `make eval-report`. OpenRouter accepts OpenAI-compatible chat completion requests
at `https://openrouter.ai/api/v1/chat/completions`; the application sends optional
`HTTP-Referer` and `X-OpenRouter-Title` attribution headers.

The API's generic `LLM_*` settings automatically fall back to the corresponding
`OPENROUTER_*` settings. Therefore the same OpenRouter configuration powers both
standalone evaluations and API assessment/summary/outreach requests unless explicit
`LLM_*` values are provided.
