"""Add durable dataset run and current pointer tracking."""
from alembic import op

revision = "0002_dataset_runs"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    create table dataset_runs (
        run_id text primary key,
        dataset_name text not null default 'companies',
        dataset_version text not null,
        source_url text not null,
        source_checksum text,
        source_etag text,
        output_uri text,
        manifest_uri text,
        checkpoint_uri text,
        status text not null default 'running',
        current_record integer not null default 0,
        next_record integer not null default 1,
        target_record integer,
        processed_rows integer not null default 0,
        company_count integer not null default 0,
        score_version text not null,
        is_current boolean not null default false,
        metadata_json jsonb not null default '{}'::jsonb,
        started_at timestamptz not null default now(),
        updated_at timestamptz not null default now(),
        completed_at timestamptz,
        error_message text
    );
    create unique index dataset_runs_current_idx
        on dataset_runs (dataset_name) where is_current = true;
    create index dataset_runs_version_idx
        on dataset_runs (dataset_name, dataset_version);
    create index dataset_runs_status_idx
        on dataset_runs (dataset_name, status, updated_at desc);
    """)


def downgrade() -> None:
    op.execute("drop table if exists dataset_runs cascade")
