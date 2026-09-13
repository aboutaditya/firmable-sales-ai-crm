# Plan — Evaluation System

Component: the harnesses that measure prompt/classification quality and grade generated content, plus the versioned result artifacts.

Source of truth files:
- `evals/README.md`, `evals/results/README.md`
- `evals/harness.py`
- `evals/harness_output.py`
- `evals/run_openrouter_eval.py`
- `evals/datasets/*`
- Make targets: `eval-openrouter`, `eval-openrouter-v2`, `eval-report`, `eval-compare`, `eval-output-*`

## Purpose

Two independent measurements:

1. **Classification quality** — how good is an account-scoring prompt/model at predicting the labelled priority?
2. **Output quality** — is generated outreach/summary content grounded in the company profile (no invented signals, no fabrication, sensible length, CTA)?

The output eval is deterministic (no second model call): it grades rows from the production trace sink.

## Datasets

| Dataset | Rows | Contents |
| --- | --- | --- |
| `datasets/account_scoring.jsonl` | 25 | Normalized company profile + `expected_priority` + `expected_score`; covers critical vulns, RDP/DB exposure, EOL, large surfaces, sparse profiles, shared-host traps, clean accounts |
| `datasets/output_rubric.jsonl` | 10 | Engineered cases (3 real traced outputs + 7 synthetic), each failing exactly one criterion; golden expectations per criterion |

## Classification harness (`harness.py`)

Reads cases + predictions, computes:

- HIGH-priority **precision / recall / F1**,
- **priority accuracy**,
- **score MAE** (predicted `ai_score` vs `expected_score`).

`compare_results` reports deltas against a previous prompt version. Fails if any case has no prediction.

## Output rubric (`harness_output.py`)

Criterion per piece of generated content, graded against the same profile found in the trace `request`:

- `covers_signal` — references an observed signal.
- `no_invented_signal` — no signals absent from the profile.
- `no_fabrication` — no assertive breach claims, no leftover `{{}}`/`[Placeholder]` tokens.
- `has_subject` (outreach only).
- `word_count_ok` — ≤150 outreach, ≤120 summary.
- `has_cta` (outreach only).

Modes: `--traces` (grade `data/traces/llm_calls.jsonl`), `--storage` (grade the `llm-traces` Storage bucket), `--golden` (verify the rubric against the golden set). Also validates classification rows via `validate_classification`.

## Prediction runner (`run_openrouter_eval.py`)

Runs the production `OpenAICompatibleProvider` over the labelled set with a chosen prompt (default v1), renders `{{company_profile}}`, and writes one prediction JSONL row per case (priority, score, confidence, reasoning, model, prompt version, latency, tokens, cost). `--resume` skips already-predicted cases so interrupted runs are never lost. Costs come from `OPENROUTER_INPUT/OUTPUT_COST_PER_1K`.

## Makefile targets

| Target | Action |
| --- | --- |
| `make eval-openrouter` | v1 predictions over 25 cases (resumable) → `results/openrouter-predictions.jsonl` |
| `make eval-openrouter-v2` | v2 predictions (resumable) → `results/openrouter-predictions-v2.jsonl` |
| `make eval-report` | harness metrics for v1 → `results/openrouter-account-scoring-v1.json` |
| `make eval-compare` | v2 vs v1 comparison |
| `make eval-output-golden` | rubric vs golden cases → `results/output-rubric.json` |
| `make eval-output-traces` | rubric on the local trace file |
| `make eval-output-storage` | rubric on the live Storage bucket traces |

## Recorded results

- **v1** (`openrouter/free`, all 25 cases): priority accuracy 0.56, high-priority P/R/F1 0.455 / 0.714 / 0.556, score MAE 15.0.
- **v2** (partial, 18-case overlap after the free-model daily quota): accuracy 0.611, P/R/F1 0.636 / 1.0 / 0.778, MAE 10.2. The partial run is explicitly labelled; the runner is resumable to finish it.
- **Output rubric** vs golden set: perfect clean-pass accuracy on the engineered cases.

## Design notes

- Real measurements come from real runs; partial runs are labelled, never silently presented as final.
- The eval exists to answer "how do you know the prompt is better?" — via a prompt-version comparison, not opinion.
- In production, evals run on a paid mid-tier model as a scheduled job, not on the free router.

## Integration points

- Traces read by the output eval: [`07-ai.md`](07-ai.md)
- Prompt files under test: [`07-ai.md`](07-ai.md)
- Run via: [`11-deployment.md`](11-deployment.md)