# How We Built It

The dev loop was agentic and small: map the repository and data, compare the
state against the take-home rubric, apply one scoped change, then verify with a
focused test before the broader suite. The biggest win came from doing this
rather than adding features.

## What happened, in order

1. **Measured before optimizing.** The eval harness existed but only had
   smoke-fixture results; no real model had been run against the 25-case
   labelled set. Running `make eval-openrouter` over all 25 cases produced the
   first real measurement: v1 F1 0.556, recall 0.714, score MAE 15.0 on the
   `openrouter/free` model. This is an honest, defensible number — the free
   router is weak, so the result is a floor, not the ceiling.
2. **The eval surfaced a real bug.** Two cases in, the run crashed because
   `openrouter/free` returned prose instead of JSON. That is a production
   failure mode, so the provider was fixed to do one bounded self-correcting
   retry (summing tokens/cost across the repair), with unit tests. The v2 run
   then hit the provider's free-model daily quota at 18/25 cases; the runner was
   made resumable (`--resume`) so partial runs are not thrown away, and the
   partial v1-vs-v2 comparison was recorded and labelled correctly instead of
   being hidden.
3. **Turned the trace data into a cost model.** The eval traces had real token
   and latency numbers (median ~1,330 tokens/call, 9.7s latency), which became
   the worked example in `architecture.md` — including the argument for capping
   output tokens and a concrete $/month ceiling math for a 100-rep team.
4. **Packaged the reproducibility work.** A `docs/deployment-plan.md`,
   `railway.toml`, and `frontend/vercel.json` now encode exactly how to host the
   two units, plus the order of operations. The repo was initialized and readied
   for push; the push and the actual deploy need service accounts this session
   could not create.

## Where AI saved the most time

- Finding the mismatch between README, checklist, and the actual measured state
  (evals claimed confidence the artifacts did not back).
- Surfacing the non-JSON failure mode through a real run instead of reasoning
  about it — the run *was* the review.
- Turning repeated “AI-native” requirements (skills, prompts, traces, cost
  math) into concrete artifacts quickly.

## Where it cost more than doing it by hand

The eval's own trap: chasing numbers. The free-router model is slow (up to 77s
per call) and verbose, so each full 25-case run took several minutes and hit
daily quotas. Cheap here, but in production the eval itself must run on a paid
mid-tier model as a scheduled job, not ad hoc.

## Known weakness to flag

The source is an external observation dataset, not a CRM or intent dataset. A
high exposure score is a reason to research an account, not evidence of buying
intent — the docs and UI say so, but a teammate must keep that discipline in
every new surface (outreach copy, dashboard copy, API naming). Second: the v2
eval is still 18/25 until the free-model quota resets and `make
eval-openrouter-v2` is re-run; the partial comparison is labelled, not silently
treated as final.