"""Create the application schema represented by the SQLAlchemy models."""
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    create table companies (
        id text primary key, domain text not null, organization text, country text,
        city text, industry text, employee_count integer,
        security_score integer not null check (security_score between 0 and 100),
        score_version text not null, dataset_version text not null,
        is_active boolean not null default true,
        created_at timestamptz not null default now(), updated_at timestamptz not null default now()
    );
    create index companies_score_idx on companies (security_score desc);
    create index companies_country_score_idx on companies (country, security_score desc);
    create index companies_industry_score_idx on companies (industry, security_score desc);
    create table company_signals (
        company_id text primary key references companies(id) on delete cascade,
        asset_count integer not null default 0, unique_ip_count integer not null default 0,
        unique_domain_count integer not null default 0, vulnerability_count integer not null default 0,
        critical_vulnerability_count integer not null default 0, eol_product_count integer not null default 0,
        exposed_rdp boolean not null default false, exposed_database boolean not null default false,
        exposed_exchange boolean not null default false, security_tag_count integer not null default 0,
        updated_at timestamptz not null default now()
    );
    create index company_signals_filter_idx on company_signals (exposed_rdp, exposed_database, exposed_exchange);
    create table ai_assessments (
        id bigserial primary key, company_id text not null references companies(id) on delete cascade,
        ai_score integer, priority text, confidence numeric(4, 3), reasoning text,
        model text not null, prompt_version text not null, input_tokens integer, output_tokens integer,
        cost_usd numeric(12, 6), latency_ms integer, created_at timestamptz not null default now()
    );
    create table ai_outputs (
        id bigserial primary key, company_id text not null references companies(id) on delete cascade,
        feature text not null, content text not null, model text not null, prompt_version text not null,
        input_tokens integer, output_tokens integer, cost_usd numeric(12, 6), latency_ms integer,
        created_at timestamptz not null default now()
    );
    create index ai_outputs_lookup_idx on ai_outputs (company_id, feature, prompt_version, created_at desc);
    create table pipeline_runs (
        id bigserial primary key, run_type text not null, dataset_version text not null,
        score_version text not null, source text not null, processed_count integer not null default 0,
        qualified_count integer not null default 0, started_at timestamptz not null default now(),
        completed_at timestamptz, status text not null, error_message text
    );
    create table audit_events (
        id bigserial primary key, actor_user_id text not null, actor_role text not null,
        action text not null, resource_type text not null, resource_id text,
        event_metadata jsonb not null default '{}'::jsonb, created_at timestamptz not null default now()
    );
    create index audit_events_actor_idx on audit_events (actor_user_id, created_at desc);
    create index audit_events_resource_idx on audit_events (resource_type, resource_id, created_at desc);
    create table company_assignments (
        company_id text not null references companies(id) on delete cascade,
        user_id text not null, team_id text, assigned_by text not null,
        created_at timestamptz not null default now(), primary key (company_id, user_id)
    );
    create index company_assignments_user_idx on company_assignments (user_id, company_id);
    """)


def downgrade() -> None:
    op.execute("drop table if exists company_assignments, audit_events, pipeline_runs, ai_outputs, ai_assessments, company_signals, companies cascade")
