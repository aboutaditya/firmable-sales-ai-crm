# Account Scoring Skill

Version: `account-scoring-v1`

## Purpose

Turn a deterministic company exposure profile into a sales qualification
decision. This workflow explains observed evidence; it must not invent a breach,
contact, business initiative, purchase intent, or company fact.

## Trigger

Run when a company has passed deterministic prequalification, normally when its
exposure score is at least the configured AI threshold. Do not call the model
for every raw observation or for accounts that fail the prequalification gate.

## Inputs

- Company profile: `company_id`, domain, organization, country, city, industry,
  and employee count when available.
- Observed signals: asset counts, vulnerability counts, critical vulnerability
  counts, EOL product count, exposed RDP/database/Exchange, and security tags.
- `score_version` and deterministic exposure score.
- Prompt file: `prompts/account_scoring/v1.txt`.
- Model and cost configuration.

## Output

Return only the validated JSON schema:

```json
{
  "ai_score": 0,
  "priority": "HIGH | MEDIUM | LOW",
  "confidence": 0.0,
  "reasoning": "Evidence-based qualification rationale"
}
```

`ai_score` is a qualification estimate, not a replacement for the deterministic
exposure score. `reasoning` must distinguish observed facts from uncertainty.

## Rules and validation

1. Use only the supplied profile and signals.
2. Never infer buying intent from exposure alone.
3. Mention the strongest one or two observed signals.
4. Lower confidence when the profile is sparse or attribution is uncertain.
5. Validate score range, priority enum, confidence range, and non-empty reasoning.
6. Persist model, prompt version, token usage, latency, cost, decision, and trace ID.

## Dependencies

- `prompts/account_scoring/v1.txt`
- `sales_intelligence.backend.ai.provider.OpenAICompatibleProvider`
- `sales_intelligence.backend.ai.schemas.QualificationResult`
- A trace sink for successful and failed calls.

## Worked invocation

Input:

```json
{
  "company_id": "acme.com",
  "security_score": 75,
  "score_version": "v1",
  "critical_vulnerability_count": 1,
  "vulnerability_count": 2,
  "exposed_rdp": true,
  "exposed_database": true,
  "eol_product_count": 1,
  "country": "US"
}
```

Invocation:

```text
Run account-scoring-v1 for acme.com after the deterministic prequalification
gate. Return schema-valid JSON and cite only the supplied observed signals.
```

Expected shape:

```json
{
  "ai_score": 88,
  "priority": "HIGH",
  "confidence": 0.9,
  "reasoning": "The account has a critical vulnerability, exposed RDP and an exposed database; buying intent is unknown."
}
```
