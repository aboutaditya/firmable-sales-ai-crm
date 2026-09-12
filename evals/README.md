# Account Scoring Evals

The evaluation harness scores saved AI predictions against a hand-labelled
dataset. It does not call an LLM itself; generate predictions separately and
evaluate the exact output that would be persisted by the application.

## Labelled set

`evals/datasets/account_scoring.jsonl` contains 25 hand-labelled cases spanning
the qualification guidance: critical vulnerabilities, exposed RDP/databases,
EOL products, large attack surfaces, sparse profiles, cloud/shared-host
attribution traps, and clean accounts. Each row has `company_id`, the normalized
`company` profile (the exact input the product would pass to the model), and the
expert labels `expected_priority` and `expected_score`.

## One-command reproduction

Generate predictions for the current prompt on OpenRouter, then report metrics:

```bash
make eval-openrouter       # account-scoring-v1 over all 25 cases
make eval-report           # precision / recall / F1 / MAE report
```

Compare a new prompt version against the current baseline:

```bash
make eval-openrouter-v2    # account-scoring-v2 predictions (resumable)
make eval-compare          # v2 metrics vs the v1 baseline
```

Both prediction targets are resumable (`--resume`): company IDs already present
in the output file are skipped, so a run interrupted by a provider outage or
rate limit can be continued instead of restarted. This mirrors the ETL
checkpoint behavior.

## Measured results

Generated 2026-09-12 with model `openrouter/free` (a free aggregate router
model on OpenRouter). These are real model measurements over the labelled set.

### v1 — `sales_intelligence/prompts/account_scoring/v1.txt` (25/25 cases)

```json
{
  "priority_accuracy": 0.56,
  "high_priority_precision": 0.455,
  "high_priority_recall": 0.714,
  "high_priority_f1": 0.556,
  "score_mae": 15.0
}
```

### v2 — `sales_intelligence/prompts/account_scoring/v2.txt` (partial: 18/25 cases)

The v2 run hit the OpenRouter free-model daily request quota after 18 cases.
The comparison below is computed on the 18-case overlap only and is labeled
`account-scoring-v2-partial`. Rerun `make eval-openrouter-v2` after the quota
resets to complete the remaining 7 cases and regenerate the full comparison.

```json
{
  "examples": 18,
  "priority_accuracy": 0.611,
  "high_priority_precision": 0.636,
  "high_priority_recall": 1.0,
  "high_priority_f1": 0.778,
  "score_mae": 10.2
}
```

Deltas vs v1 on the same 18 cases: F1 `+0.064`, recall `+0.286`, precision
`-0.078`, accuracy `-0.056`, score MAE `-2.67` (better).

## Generated-output eval (outreach / summary)

Classification metrics do not apply to free-form output, so the generative
flows are graded with an evidence rubric in `evals/harness_output.py`. The
rubric checks each generated message against the observed profile that was in
the same request:

- `covers_signal` — references at least one signal actually present in the
  profile (nothing to cover when the profile has no signals → not scored).
- `no_invented_signal` — never names a signal class the profile lacks
  (negated mentions such as "no critical vulnerabilities" are not penalties).
- `no_fabrication` — no assertive breach/compromise claims
  ("not evidence of a breach" passes; "we detected a breach" fails) and no
  un-filled template placeholders.
- `has_subject` (outreach) — output starts with a subject line.
- `word_count_ok` — ≤150 words for outreach, ≤120 for summaries (the prompt's
  explicit and implied limits).
- `has_cta` (outreach) — ends with an invitation or question.

Two modes, both deterministic and LLM-free:

```bash
make eval-output-golden   # rubric vs the hand-labelled cases (evals/datasets/output_rubric.jsonl)
make eval-output-traces   # score the real outputs already in data/traces/llm_calls.jsonl
make eval-output-storage  # score the outputs uploaded to the Supabase Storage bucket
```

The golden set has 10 cases: the 3 real outputs captured in the trace file plus
7 synthetic cases, each engineered to fail exactly one criterion. Current
results: rubric agrees with all 10 labels (clean-pass accuracy 1.0, 1.0
precision/recall per criterion), and all 3 real traced outputs clean-pass. See
`evals/results/README.md`.

Produced traces reach the evaluation two ways. Locally, `data/traces/llm_calls.jsonl`
(line for line JSON). In production, `LLM_TRACE_BACKEND=storage` uploads each
record as an object to the `llm-traces` bucket at
`traces/<prompt-version>/<year>/<month>/<day>/` — one record per object so
concurrent serverless instances cannot clobber each other — and
`--storage`/`make eval-output-storage` reads that prefix with the service-role
key and reassembles the JSONL stream.

Measured weaknesses of the rubric itself: `no_invented_signal` treats
comma-separated negations conservatively ("no X, Y were found" negates X but
not Y after the comma), and word-count includes subject lines and signatures,
so a >150-word body can still pass if headers are short. The rubric measures
*claim accuracy against the source profile*, not copy quality; tone and
persuasiveness still need a human read.

## Known weaknesses

- **Free router model quality is the ceiling, not the floor.** `openrouter/free`
  aggregates no-cost models that are far weaker than the paid classifier we
  would ship in production. Score MAE of 15 on v1 means the model often assigns
  plausible but imprecise scores; precision at 0.45 means it over-calls HIGH on
  accounts experts would not rush to. Do not tune prompts against this model to
  chase score; the gate for shipping a production model should be a paid eval
  run (e.g. a `gpt-*` or `claude-*` slug) with cost surfaced from the trace sink.
- **Verbosity drives cost.** The free router emitted ~1,178 median output
  tokens per classification (max 77s latency). A production classifier should
  either constrain output tokens or use a cheaper targeted model; the eval does
  not yet measure the token savings of doing that.
- **Attribution traps are only partially handled.** `cloud-provider.example`
  (shared hosting attribution) and sparse `unknown-company.example` cases are
  in the set precisely because the free model tends to over-prioritize them.

## Prediction format

Each generated prediction line:

```json
{"company_id":"acme.com","priority":"HIGH","ai_score":73,"model":"openrouter/free","prompt_version":"account-scoring-v1","latency_ms":...}
```

The OpenRouter runner records model, version, latency, and token usage; cost is
populated when the provider reports pricing (`OPENROUTER_INPUT_COST_PER_1K` /
`OPENROUTER_OUTPUT_COST_PER_1K`).