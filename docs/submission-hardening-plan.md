# Submission Hardening Plan

This plan turns the take-home requirements into a small sequence of shippable
changes. The product should help a salesperson choose the next account to work,
understand why it is prioritized, and produce evidence-based outreach.

## Baseline findings

- The Python suite now covers API behavior and queue isolation; the frontend
  production build passes.
- The committed demo Parquet artifact is intentionally small and reproducible,
  with varied score bands so the local queue opens with useful accounts.
- The account-scoring eval has 25 labelled examples and the harness compares
  prompt versions.
- Reusable workflows currently live under `docs/skills/*.md`, while the brief
  requires `skills/**/SKILL.md`.
- The current score measures observed security exposure, not ICP fit or buying
  intent. Product copy must make that distinction explicit.

## Implementation order

### 1. Required AI workflow packaging

- [x] Add `skills/account-scoring/SKILL.md`.
- [x] Add `skills/outreach-draft/SKILL.md`.
- [x] Add worked invocation examples and validation details.
- [x] Update references from `docs/skills`.

### 2. Evaluation quality and prompt comparison

- [x] Expand the hand-labelled account-scoring set to 20–30 representative cases.
- [x] Add a second prompt version.
- [x] Make the harness run and compare two prompt versions in one command.
- [x] Store versioned results and document known weaknesses. v1 measured over
  all 25 cases; v2 measured over the 18-case overlap after the free-model daily
  quota interrupted the run. Results and weaknesses are documented in
  `evals/README.md`; `evals/results/README.md` records which artifacts are
  complete vs partial and how to finish the v2 run.

### 3. Complete LLM observability and cost model

- [x] Add a central JSONL trace sink for successful and failed LLM calls.
- [x] Persist request, response, model, prompt version, latency, tokens, cost,
  decision, and trace ID.
- [x] Document model selection, token assumptions, volume, frequency, budget,
  and production cost ceiling.

### 4. Sales-oriented scoring and product language — in progress

- [x] Rename or clarify the deterministic score as an exposure score.
- [ ] Add explicit ICP-fit/data-completeness fields where source data supports it.
- [x] Keep buying intent separate from observed security need.
- [x] Explain observed evidence in the UI.

### 5. Non-empty, trustworthy demo dataset — in progress

- [x] Replace the empty smoke-test experience with a reproducible demo fixture
  containing varied companies and score bands.
- [x] Keep the provided dataset central and label bounded runs honestly.
- [ ] Add a visible dataset version/source indicator.

### 6. Sales workflow UI — in progress

- [x] Add a clear “why this account?” evidence view.
- [x] Add a one-lead personal queue with a user-level threshold.
- [x] Add assignment-scoped dispositions, notes, follow-up, and call activity.
- [x] Keep summary and outreach as separate, optional AI actions.
- [x] Block sales representatives from the global company list.

### 7. Submission documentation and hosting — in progress

- [x] Rewrite planning around territory prioritization, account qualification,
  and outreach.
- [x] Rewrite architecture around data flow, rule-vs-LLM boundaries, traces,
  and cost (including the measured cost work-through).
- [x] Add `docs/how-we-built.md`.
- [x] Add `docs/deployment-plan.md`, `railway.toml`, and `frontend/vercel.json`
  with the exact env vars and deployment order.
- [x] Initialize the local Git repository with a first commit.
- [ ] Push the repository and deploy the app with a working URL (requires a
  GitHub account and Railway/Vercel accounts; see `docs/deployment-plan.md`).
- [ ] Complete the v2 eval run once the OpenRouter free-model quota resets
  (`make eval-openrouter-v2 && make eval-compare`).

## Definition of done

The hosted demo opens with useful prospects, shows the evidence behind a
priority, lets a reviewer filter a segment, runs the core AI workflow, and links
every AI result to a versioned prompt, trace, and evaluation result. The docs
should explain limitations rather than imply that observed exposure proves
purchase intent.
