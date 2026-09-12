# Evaluation results

Measured artifacts from the OpenRouter runs. See `../README.md` for the labelled
set, reproduction commands, and known weaknesses.

| Artifact | Scope | Status |
| --- | --- | --- |
| `openrouter-predictions.jsonl` | v1 prompt, 25/25 cases | Complete (2026-09-12) |
| `openrouter-account-scoring-v1.json` | v1 report | Complete |
| `openrouter-predictions-v2.jsonl` | v2 prompt, 18/25 cases | **Partial** — run hit the free-model daily quota; resume with `make eval-openrouter-v2` |
| `openrouter-account-scoring-v2-partial.json` | v2 report vs v1 subset | Partial — 18-case overlap |
| `openrouter-predictions-v1-18subset.jsonl` | v1 rows for the 18 shared cases | Derived artifact for the partial comparison |
| `cases-18subset.jsonl` | cases for the 18 shared companies | Derived artifact for the partial comparison |

## Regenerate the full v1 vs v2 comparison

The free-model daily quota resets by ~00:00 UTC each day. Once reset:

```bash
make eval-openrouter-v2    # completes the missing 7 cases (resumable)
make eval-compare          # writes openrouter-account-scoring-v2.json
```

Then remove the two `*-18subset` derived files and this partial entry, and add
the full `openrouter-account-scoring-v2.json` row above.