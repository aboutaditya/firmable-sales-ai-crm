Absolutely. Based on the approach we've converged on, I would make the HLD **less infrastructure-heavy and more product/data-pipeline focused**. The key architectural idea is:

> **Process the 11GB raw dataset once → aggregate to company-level data → store the analytical dataset in Parquet → use DuckDB for scoring/ranking → persist only sales-relevant companies and AI assessments in Supabase → serve the product through FastAPI/Next.js.**

# **High-Level Design — AI Sales Intelligence Platform**

## **1\. Goal**

Build a sales intelligence platform that helps sales teams answer:

> **“Which companies are most likely to need our cybersecurity product, and which prospects should I contact first?”**

The system transforms raw infrastructure/security observations into:

1. **Company-level security signals**  
2. **Deterministic cybersecurity score**  
3. **Ranked prospects**  
4. **AI-assisted qualification and explanation**  
5. **Search/filtering for sales teams**  
6. **Outreach recommendations**

The architecture is designed to process the provided \~11GB compressed dataset without loading it entirely into memory or storing the raw dataset in the application database.

---

# **2\. High-Level Architecture**

                        ┌──────────────────────┐  
                         │   Raw Dataset        │  
                         │   \~11GB .zst JSONL   │  
                         └──────────┬───────────┘  
                                    │  
                                    │ Streaming  
                                    ▼  
                         ┌──────────────────────┐  
                         │   Python ETL         │  
                         │                      │  
                         │ Parse                │  
                         │ Validate             │  
                         │ Normalize            │  
                         │ Aggregate            │  
                         │ Deduplicate          │  
                         └──────────┬───────────┘  
                                    │  
                                    ▼  
                         ┌──────────────────────┐  
                         │ Company Profiles     │  
                         │ \~100K companies      │  
                         └──────────┬───────────┘  
                                    │  
                                    ▼  
                         ┌──────────────────────┐  
                         │      Parquet         │  
                         │ Processed analytical  │  
                         │ dataset              │  
                         └──────────┬───────────┘  
                                    │  
                                    ▼  
                         ┌──────────────────────┐  
                         │       DuckDB         │  
                         │                      │  
                         │ Feature calculation  │  
                         │ Deterministic score  │  
                         │ Ranking              │  
                         │ Filtering            │  
                         └──────────┬───────────┘  
                                    │  
                         score \>= threshold  
                                    │  
                                    ▼  
                         ┌──────────────────────┐  
                         │ Qualified Companies  │  
                         │ \~5K–10K              │  
                         └──────────┬───────────┘  
                                    │  
                         ┌──────────┴──────────┐  
                         │                     │  
                         ▼                     ▼  
                ┌─────────────────┐   ┌──────────────────┐  
                │    Supabase     │   │ Parquet/DuckDB   │  
                │   PostgreSQL    │   │ Analytical data  │  
                │                 │   │                  │  
                │ App data        │   │ Reprocessing     │  
                │ Scores          │   │ Re-ranking       │  
                │ AI assessments  │   │                  │  
                │ User state      │   │                  │  
                └────────┬────────┘   └──────────────────┘  
                         │  
                         ▼  
                ┌─────────────────┐  
                │    FastAPI      │  
                │     Backend     │  
                └────────┬────────┘  
                         │  
                         ▼  
                ┌─────────────────┐  
                │    Next.js      │  
                │   Sales UI      │  
                └─────────────────┘  
---

# **3\. Data Ingestion**

The provided dataset is approximately **11GB compressed** and contains individual infrastructure/security observations rather than clean company records.

Examples of information observed in the dataset include:

IP  
hostname  
domain  
organization  
location  
port  
product  
OS  
CPE  
tags  
vulnerabilities  
HTTP information  
SSL information  
cloud information

The system therefore should **not attempt to upload the raw dataset directly into Postgres**.

Instead, the dataset is treated as an immutable raw source.

raw/  
└── dataset.zst

### **Processing characteristics**

The ETL process:

* Reads the compressed JSONL stream sequentially  
* Processes one record at a time  
* Extracts relevant fields  
* Normalizes inconsistent values  
* Aggregates records by company/domain  
* Writes company-level records  
* Does not require the entire 11GB dataset in memory

Conceptually:

for record in stream(dataset):  
    company \= normalize\_company(record)

    aggregate\[company\].update(  
        extract\_security\_signals(record)  
    )

For a production-scale implementation, aggregation can also be performed using partitioned intermediate files rather than maintaining all state in memory.

---

# **4\. Company Aggregation**

The raw dataset is observation-oriented.

For example:

IP 1 → port 3389 → Microsoft RDP  
IP 2 → port 443  → nginx  
IP 3 → MySQL  
IP 4 → vulnerability  
IP 5 → Exchange

The sales team doesn't want to see five individual infrastructure records.

They want:

Acme Corp  
────────────────────  
5 exposed assets  
2 RDP endpoints  
1 database  
3 vulnerabilities  
1 critical vulnerability  
1 EOL product

Therefore we transform:

Raw observations  
       ↓  
Company aggregation  
       ↓  
Company profile

Example:

{  
  "company\_id": "acme.com",  
  "domain": "acme.com",  
  "organization": "Acme Corp",  
  "country": "US",  
  "asset\_count": 57,  
  "unique\_ip\_count": 41,  
  "unique\_domain\_count": 12,  
  "vulnerability\_count": 18,  
  "critical\_vulnerability\_count": 3,  
  "eol\_product\_count": 4,  
  "exposed\_rdp": true,  
  "exposed\_database": true,  
  "exposed\_exchange": false  
}  
---

# **5\. Analytical Storage — Parquet**

After aggregation, the data should be stored as **Parquet**.

data/  
├── raw/  
│   └── dataset.zst  
│  
└── processed/  
    └── companies.parquet

The raw 11GB dataset may reduce to roughly **tens to low hundreds of MB** once aggregated to \~100K companies, depending on the number and size of retained fields.

A reasonable planning estimate is:

Raw dataset:              \~11 GB  
Company Parquet:          \~20–150 MB

The exact number should be measured after the first ETL run rather than assumed.

### **Why Parquet?**

Parquet provides:

* Columnar storage  
* Compression  
* Efficient analytical queries  
* Predicate pushdown  
* Smaller storage footprint  
* Easy integration with DuckDB

---

# **6\. DuckDB**

DuckDB is the **analytical/query engine**, not necessarily the permanent application database.

It can query Parquet directly:

SELECT \*  
FROM 'companies.parquet'  
WHERE security\_score \>= 60  
ORDER BY security\_score DESC  
LIMIT 500;

This gives us a very useful separation:

Parquet  
   ↓  
DuckDB  
   ↓  
Analytics / scoring / ranking

We don't have to maintain another large database containing the entire processed dataset.

---

# **7\. Deterministic Scoring Engine**

The first stage of prospect qualification should be **deterministic**, not LLM-based.

This makes the system:

* Explainable  
* Cheap  
* Reproducible  
* Fast  
* Easy to evaluate

Example scoring:

Security Exposure  
────────────────────────────  
Critical vulnerability      \+20  
Multiple vulnerabilities     \+10  
Exposed RDP                  \+15  
Exposed database             \+15  
EOL technology               \+10  
Large external attack surface \+10  
Security-related tags         \+5  
────────────────────────────  
Maximum                       100

The actual weights should be documented and justified based on cybersecurity sales use cases.

The output:

company\_id  
security\_score  
score\_version

Example:

acme.com       87    v1  
foo.com        71    v1  
bar.com        42    v1  
---

# **8\. Why We Don't Store Only Top 500**

This is an important architectural decision.

We **do not** do:

100K  
 ↓  
Top 500  
 ↓  
Supabase

because this makes the system inflexible.

For example:

> "Show me the top cybersecurity prospects in Germany."

The 501st company globally could actually be the \#1 German prospect.

Instead:

100K companies  
      ↓  
Deterministic score  
      ↓  
Score threshold  
      ↓  
\~5K–10K qualified companies  
      ↓  
Supabase

The application can then dynamically request:

Top 10  
Top 50  
Top 100  
Top 500  
Top 1000

without rerunning ETL.

---

# **9\. Supabase / PostgreSQL**

Supabase becomes the **application database**, not the raw-data warehouse.

It stores the smaller sales-relevant dataset.

For example:

companies  
────────────────────────────  
id  
domain  
organization  
country  
city  
employee\_count  
security\_score  
score\_version  
created\_at  
updated\_at

And security signals:

company\_signals  
────────────────────────────  
company\_id  
asset\_count  
vulnerability\_count  
critical\_vulnerability\_count  
eol\_count  
exposed\_rdp  
exposed\_database  
exposed\_exchange

And AI assessments:

ai\_assessments  
────────────────────────────  
company\_id  
ai\_score  
priority  
reasoning  
model  
prompt\_version  
input\_tokens  
output\_tokens  
cost  
latency  
created\_at

Supabase should therefore only contain the data required for the product.

---

# **10\. Dynamic Lead Ranking**

Suppose the salesperson asks:

> Give me the top 10 companies.

The system performs:

SELECT \*  
FROM companies  
ORDER BY security\_score DESC  
LIMIT 10;

For:

> Give me the top 500

it becomes:

SELECT \*  
FROM companies  
ORDER BY security\_score DESC  
LIMIT 500;

For:

> Give me the top 100 cybersecurity prospects in the US.

SELECT \*  
FROM companies  
WHERE country \= 'US'  
ORDER BY security\_score DESC  
LIMIT 100;

No raw data processing is required.

---

# **11\. LLM Qualification Layer**

The LLM should be used **after deterministic filtering**, rather than scoring every raw record.

100K companies  
      ↓  
Deterministic scoring  
      ↓  
\~5K–10K qualified  
      ↓  
Sales filters  
      ↓  
Top candidates  
      ↓  
LLM

The LLM can perform tasks where reasoning/free-text understanding is useful:

### **Account qualification**

Input:  
Company profile \+ security signals

Output:  
\- ICP fit  
\- buying likelihood  
\- priority  
\- reasoning

### **Company summary**

"Why should a salesperson care about this company?"

### **Outreach**

Generate a personalized first-touch email  
based on the company's observed signals.

This keeps LLM usage focused on **high-value decisions**.

---

# **12\. Rule vs LLM Split**

This should be explicitly documented in the architecture.

| Task | Approach | Reason |
| ----- | ----- | ----- |
| Parse JSONL | Rule | Deterministic |
| Normalize domains | Rule | Deterministic |
| Aggregate assets | Rule | Deterministic |
| Count vulnerabilities | Rule | Deterministic |
| Detect exposed RDP | Rule | Exact signal |
| Calculate security score | Rule | Explainability |
| Filter country | Rule | Exact |
| Filter company size | Rule | Exact |
| Rank candidates | Rule | Fast/cheap |
| ICP judgement | LLM | Requires reasoning |
| Company summary | LLM | Natural language |
| Outreach generation | LLM | Natural language |
| Explain complex signals | LLM | Reasoning |

The principle is:

> **Use deterministic logic whenever the problem has a deterministic answer. Use the LLM where interpretation or natural-language reasoning provides value.**

---

# **13\. AI Observability**

Every LLM call should generate a trace.

Example JSONL:

{  
  "timestamp": "2026-09-10T15:30:00Z",  
  "company\_id": "acme.com",  
  "feature": "account\_scoring",  
  "model": "claude-model",  
  "prompt\_version": "account-scoring-v2",  
  "input\_tokens": 850,  
  "output\_tokens": 210,  
  "latency\_ms": 1420,  
  "cost\_usd": 0.0021,  
  "decision": "HIGH\_PRIORITY"  
}

This allows us to answer:

* What model was used?  
* Which prompt version?  
* How many tokens?  
* How much did it cost?  
* How long did it take?  
* What decision did it make?

---

# **14\. Prompt Versioning**

Prompts live in Git:

prompts/  
├── account\_scoring/  
│   ├── v1.txt  
│   └── v2.txt  
│  
├── company\_summary/  
│   └── v1.txt  
│  
└── outreach/  
    └── v1.txt

A database/log record references:

feature \= account\_scoring  
prompt\_version \= v2

This allows us to compare:

v1 → precision 72%  
v2 → precision 84%  
---

# **15\. Skills**

Reusable AI workflows are defined under:

skills/  
├── account-scoring/  
│   └── SKILL.md  
│  
└── outreach-draft/  
    └── SKILL.md

A skill describes:

Trigger  
Inputs  
Expected outputs  
Prompt  
Dependencies  
Validation  
Example invocation

For example:

skills/account-scoring/SKILL.md

Trigger:  
Company passes deterministic qualification threshold.

Input:  
Company profile \+ security signals.

Output:  
Priority \+ reasoning \+ confidence.

Model:  
Claude

Prompt:  
prompts/account\_scoring/v2.txt

This makes the workflow reusable by different AI development tools/agents.

---

# **16\. Evals**

The core LLM feature should have a small hand-labelled dataset.

evals/  
├── account\_scoring.jsonl  
├── harness.py  
├── results/  
│   ├── v1.json  
│   └── v2.json  
└── README.md

Example:

{  
  "company": "example.com",  
  "expected\_priority": "HIGH",  
  "expected\_reason": "Multiple critical exposures"  
}

Run:

python evals/harness.py

Output:

Account Scoring Eval

Prompt: v2

Examples: 25

Precision: 0.84  
Recall:    0.80  
F1:        0.82

Previous version: v1  
F1: 0.73

Improvement: \+12.3%

This gives you an actual answer when the interviewer asks:

> "How do you know your prompt is better?"

---

# **17\. Cost Model**

The expensive operation should be isolated.

Raw processing  
    ↓  
Python  
    ↓  
Free / infrastructure cost

Deterministic scoring  
    ↓  
DuckDB  
    ↓  
Negligible marginal cost

LLM  
    ↓  
Only qualified prospects  
    ↓  
Primary variable cost

Example:

100,000 companies  
        ↓  
Deterministic filtering  
        ↓  
10,000 qualified  
        ↓  
LLM qualification

If the average LLM cost is:

$0.002 / company

then:

10,000 × $0.002  
\= $20

The exact number should be calculated using the **actual selected model's current pricing**, rather than hardcoding the estimate.

---

# **18\. API Layer**

FastAPI sits between the UI and data services.

### **Companies**

GET /companies

Supports:

country  
industry  
score  
employee\_count  
signals  
limit  
cursor

### **Company details**

GET /companies/{company\_id}

Returns:

Company  
Security signals  
Deterministic score  
AI assessment  
Reasoning

### **AI assessment**

POST /companies/{id}/assess

Triggers LLM qualification.

### **Outreach**

POST /companies/{id}/outreach

Generates an outreach draft.

### **Evaluation**

GET /evals

Returns current evaluation metrics.

---

# **19\. Frontend**

Next.js provides the sales interface.

### **Main dashboard**

┌─────────────────────────────────────────────┐  
│ Sales Intelligence                          │  
├─────────────────────────────────────────────┤  
│ Country ▼  Industry ▼  Score ▼ Employees ▼ │  
├─────────────────────────────────────────────┤  
│                                             │  
│ Company       Score    Signals       Priority│  
│ Acme Corp      92      RDP, CVE       HIGH  │  
│ XYZ Ltd       87      EOL, CVE        HIGH  │  
│ Foo Inc       81      DB exposure     HIGH  │  
│                                             │  
└─────────────────────────────────────────────┘

### **Company detail**

Acme Corp  
Score: 92 / 100

Security Signals  
────────────────────────  
Critical vulnerabilities: 3  
Exposed RDP:              Yes  
Exposed database:         Yes  
EOL products:             4

Why this account?  
────────────────────────  
AI-generated explanation

\[ Generate Outreach \]  
---

# **20\. End-to-End Request Flow**

For:

> **"Give me the top 10 cybersecurity prospects in the US."**

The flow is:

User  
 │  
 ▼  
Next.js  
 │  
 ▼  
FastAPI  
 │  
 ▼  
Supabase  
 │  
 │ WHERE country \= US  
 │ ORDER BY security\_score DESC  
 │ LIMIT 10  
 ▼  
Top 10 companies  
 │  
 ▼  
Next.js

If the user opens one:

Company  
   ↓  
Signals  
   ↓  
Deterministic score  
   ↓  
Existing AI assessment?  
   │  
   ├── YES → return cached result  
   │  
   └── NO  
        ↓  
      LLM  
        ↓  
   Store assessment  
        ↓  
      Return

This avoids repeatedly paying for the same LLM call.

---

# **21\. Handling Score Changes**

Suppose we change:

Scoring v1

to:

Scoring v2

We **don't re-download or reprocess the 11GB dataset**.

Instead:

companies.parquet  
       ↓  
DuckDB  
       ↓  
Scoring v2  
       ↓  
new scores  
       ↓  
new ranking  
       ↓  
sync qualified companies  
       ↓  
Supabase

This is one of the main benefits of keeping the analytical layer separate from the application database.

---

# **22\. Handling Dataset Updates**

If a new raw dataset arrives:

dataset\_v2.zst  
       ↓  
Python ETL  
       ↓  
Company aggregation  
       ↓  
companies\_v2.parquet  
       ↓  
Scoring  
       ↓  
Supabase sync

The raw dataset remains immutable.

We can maintain:

dataset\_version  
score\_version  
prompt\_version

This gives us reproducibility across the entire pipeline.

---

# **23\. Deployment**

For the take-home:

                   GitHub  
                       │  
          ┌────────────┴────────────┐  
          ▼                         ▼  
       Vercel                    Railway  
       Next.js                   FastAPI  
                                     │  
                                     ▼  
                                  Supabase  
                                  PostgreSQL

The analytical dataset can remain in object storage/local processing infrastructure rather than being loaded into Supabase.

For a production architecture, Parquet files could live in object storage such as S3-compatible storage.

---

# **24\. Repository Structure**

I would structure the repository like this:

sales-intelligence/  
│  
├── backend/  
│   ├── api/  
│   ├── services/  
│   ├── models/  
│   └── main.py  
│  
├── frontend/  
│   └── next-app/  
│  
├── pipeline/  
│   ├── ingestion/  
│   ├── aggregation/  
│   ├── scoring/  
│   └── export/  
│  
├── data/  
│   └── README.md  
│  
├── prompts/  
│   ├── account\_scoring/  
│   │   ├── v1.txt  
│   │   └── v2.txt  
│   └── outreach/  
│       └── v1.txt  
│  
├── skills/  
│   ├── account-scoring/  
│   │   └── SKILL.md  
│   └── outreach-draft/  
│       └── SKILL.md  
│  
├── evals/  
│   ├── datasets/  
│   ├── harness.py  
│   └── results/  
│  
├── docs/  
│   ├── planning.md  
│   ├── architecture.md  
│   └── how-we-build.md  
│  
├── scripts/  
│   ├── run\_etl.py  
│   ├── score\_companies.py  
│   └── sync\_supabase.py  
│  
└── README.md  
---

# **25\. Final Architecture Decision**

The most important design decisions are:

### **Raw data**

**11GB `.zst` → Python streaming**

Don't put it in Postgres.

### **Analytical data**

**\~100K company profiles → Parquet**

Compact, versionable and analytical.

### **Processing/query engine**

**DuckDB**

Used for aggregation, scoring, ranking and reprocessing.

### **Application database**

**Supabase/PostgreSQL**

Store only the sales-relevant company universe, application state and AI assessments.

### **Deterministic scoring**

Used for:

* Security signals  
* Filtering  
* Ranking  
* Initial qualification

### **LLM**

Used selectively for:

* ICP judgement  
* Account qualification  
* Explanations  
* Outreach

### **AI infrastructure**

skills/  
prompts/  
evals/  
traces/  
cost tracking/

are all version-controlled and reproducible.

---

## **The core architectural principle**

I'd summarize the whole HLD in the interview as:

> **“I treat the 11GB dataset as an analytical source rather than application data. I stream it once through Python to aggregate millions of infrastructure observations into roughly 100K company profiles. Those profiles are stored compactly in Parquet and queried with DuckDB for deterministic feature calculation and scoring. I then push only the sales-relevant companies into Supabase, which becomes the application database. This allows the product to dynamically return Top 10, Top 500 or Top 1,000 without reprocessing the raw dataset. I reserve LLM calls for the smaller set of qualified accounts where reasoning adds value, and version the prompts, skills and evals while tracing every call for quality and cost.”**

That is a much stronger HLD than **“11GB → database → LLM → top leads”**, because it clearly separates **raw data processing, analytical computation, application storage, deterministic scoring, and AI reasoning**.

