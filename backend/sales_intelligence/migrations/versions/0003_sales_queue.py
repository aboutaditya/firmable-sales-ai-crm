"""Add per-user queue preferences, assignment state, and call activities."""

from alembic import op


revision = "0003_sales_queue"
down_revision = "0002_dataset_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    alter table company_assignments
        add column status text not null default 'assigned',
        add column disposition text,
        add column claimed_at timestamptz,
        add column last_contacted_at timestamptz,
        add column next_follow_up_at timestamptz,
        add column notes text,
        add column updated_at timestamptz not null default now();

    create index company_assignments_queue_idx
        on company_assignments (user_id, status, next_follow_up_at, company_id);

    create table user_preferences (
        user_id text primary key,
        min_exposure_score integer not null default 60
            check (min_exposure_score between 0 and 100),
        page_size integer not null default 1 check (page_size = 1),
        updated_at timestamptz not null default now()
    );

    create table call_activities (
        id bigserial primary key,
        company_id text not null references companies(id) on delete cascade,
        user_id text not null,
        outcome text not null,
        notes text,
        next_follow_up_at timestamptz,
        created_at timestamptz not null default now()
    );
    create index call_activities_company_idx
        on call_activities (company_id, created_at desc);
    create index call_activities_user_idx
        on call_activities (user_id, created_at desc);
    """)


def downgrade() -> None:
    op.execute("""
    drop table if exists call_activities;
    drop table if exists user_preferences;
    drop index if exists company_assignments_queue_idx;
    alter table company_assignments
        drop column if exists updated_at,
        drop column if exists notes,
        drop column if exists next_follow_up_at,
        drop column if exists last_contacted_at,
        drop column if exists claimed_at,
        drop column if exists disposition,
        drop column if exists status;
    """)
