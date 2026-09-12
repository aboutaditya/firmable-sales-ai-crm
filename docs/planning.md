# Product Plan

## Product thesis

Sales teams do not need another list of exposed hosts. They need a short,
defensible account queue: which companies deserve research first, what evidence
supports that choice, and what a safe first touch could say.

The provided dataset is observation-oriented, so the product treats observed
external exposure as a reason to investigate rather than proof of a breach or
purchase intent.

## Use case 1: a personal next-best-account queue

**User:** a sales representative working an assigned territory.

**Question:** Which one account should I work next, and can I record what
happened on the call?

**Product behavior:** representatives receive one assigned company at a time.
Their minimum exposure score is stored as a user preference, and the server
claims the next eligible assignment. Dispositions, notes, follow-up dates, and
call activities are persisted against that assignment.

**Why it matters:** a short queue is easier to act on than a shared list. The
server-side assignment check also prevents representatives from discovering
or generating AI content for another user’s accounts.

## Use case 2: territory and segment prioritization

**User:** a sales manager or representative.

**Question:** Which accounts in my country, industry, or employee band should I
work first?

**Product behavior:** filter the company-level dataset by territory and segment,
then rank by deterministic exposure score. The result shows the strongest
observed signals and keeps the source/dataset version visible.

**Why it matters:** exact filters and deterministic ranking make territory
coverage repeatable and inexpensive. AI is not needed for this step.

## Use case 3: account qualification

**User:** a representative deciding whether an account deserves research time.

**Question:** Why is this account prioritized, and what is still uncertain?

**Product behavior:** show score contributions, exposed services,
vulnerability/EOL counts, data completeness, and an AI qualification memo after
deterministic prequalification. The memo must separate facts from judgement and
state that buying intent is unknown.

**Why it matters:** the salesperson can defend the decision internally and avoid
overclaiming in outreach. The LLM adds interpretation, not new evidence.

## Use case 4: evidence-based first touch

**User:** a representative preparing an initial email.

**Question:** How can I open a relevant conversation without making a claim we
cannot support?

**Product behavior:** draft a short human-reviewable message grounded in one
observed signal, with a cautious business implication and a low-friction call
to action. The draft is never sent automatically.

**Why it matters:** it reduces preparation time while preserving trust and
avoiding invented incidents, contacts, or intent.

## Scoring approach

The current deterministic exposure score uses interpretable signal weights for
critical vulnerabilities, multiple vulnerabilities, exposed RDP, exposed
databases, EOL products, large external surface, and security-related tags.
Each score is versioned. The UI labels it as exposure, not intent.

ICP fit is intentionally separate. Industry, employee count, country, and
territory are filters when present; missing values remain unknown instead of
being fabricated or silently treated as a positive signal.

## Success criteria for the prototype

- A representative can start with one actionable account instead of a bulk
  lead table.
- A reviewer can identify a useful account from the demo in under one minute.
- Every priority has visible evidence and a score version.
- Managers can assign companies; representatives cannot browse the global
  company list.
- A representative can change their own minimum exposure threshold and record
  a disposition or call outcome.
- AI outputs are cached, traced, prompt-versioned, and evaluated.
- Outreach never claims an unobserved breach or purchase initiative.

## Scope cuts

The prototype does not attempt CRM contact discovery, automated sending,
confirmed breach detection, or real buying-intent prediction. Those require
additional sources and stronger governance than the provided dataset supports.
Manager assignment administration is currently exposed through the protected
assignment API; a manager-facing assignment screen is a follow-up once the
identity-provider user directory is connected.
