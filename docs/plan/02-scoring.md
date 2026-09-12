# Plan — Deterministic Scoring Engine

Component: the rule-based exposure score applied during ETL and used everywhere downstream for ranking, filtering, and pre-qualification. All weights and thresholds are configuration.

Source of truth files:
- `sales_intelligence/scoring.py` (`ScoringConfig`, `score`, `SCORE_VERSION`, `load_scoring_config`)
- `sales_intelligence/pipeline.py` (applies the config during `aggregate`)

## Purpose

Turn aggregated company signals into a single explainable 0–100 **exposure** score. The score measures observed external security exposure — it explicitly does **not** claim ICP fit or buying intent.

## Configuration

`ScoringConfig` holds every tuning knob; `DEFAULT_SCORING_CONFIG` matches the shipped v1 model. Override any subset of fields with a JSON file referenced by `SCORING_CONFIG_PATH` or the ETL `--scoring-config` flag — weight changes require no code edits. Each run records the effective `score_version` (`SCORE_VERSION = "v1"` by default) in every artifact.

## Default score definition (v1)

The v1 model credits a fixed ceiling per observed signal kind; every term is a config field, so weights can change without code edits. With `DEFAULT_SCORING_CONFIG`:

| Signal (any count > 0 unless noted) | Contribution |
| --- | --- |
| Critical vulnerabilities present | `+20` |
| Total vulnerabilities >= 2 | `+10` |
| Exposed RDP | `+15` |
| Exposed database | `+15` |
| Exposed Exchange | `+0` (field exists; opt-in via config) |
| EOL products present | `+10` |
| External surface: unique IPs >= 25 | `+10` |
| Security-related tags present | `+5` |

The total is capped at `max_score=100`. The result is stored on each profile as `security_score` with its `score_version` in every downstream artifact (Parquet, sync rows, API responses).

## Uses

- ETL output ordering (highest score first).
- Analytical query `min_score` filter and rank ordering.
- The sync threshold (`--min-score`, default 60) that decides which companies are promoted to Postgres.
- The AI pre-qualification gate (`AI_MIN_SCORE`) that blocks LLM spend below the deterministic threshold.

## Properties

- Deterministic: same input → same score, no randomness.
- Explainable: every contribution traces to observed `company_signals` fields surfaced in the UI.
- Free: computed at ETL time, no model cost.
- Versioned: a score change increments `SCORE_VERSION` and flows through `dataset_version`/`score_version` reporting, so results remain reproducible and comparable.

## Evolution path

Score weights and thresholds are now configurable via `ScoringConfig` (defaults = v1). Remaining follow-ups are broader signal coverage and calibration against labelled examples; a score change then increments the configured `score_version` and flows through `dataset_version`/`score_version` reporting, keeping results reproducible and comparable.

## Integration points

- Computed during aggregation: [`01-etl.md`](01-etl.md)
- Read/ranked via DuckDB: [`03-analytics-layer.md`](03-analytics-layer.md)
- Gated into Postgres: [`04-db-sync.md`](04-db-sync.md)
- Gates AI calls: [`07-ai.md`](07-ai.md)
- Displayed in the UI: [`09-frontend.md`](09-frontend.md)