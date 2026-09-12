from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

# ---------------------------------------------------------------------------
# Output rubric
#
# These checks are deterministic so the eval is reproducible and LLM-free.
# They grade the *content* an LLM produced for outreach / company_summary by
# comparing it against the observed profile that was in the same request.
# ---------------------------------------------------------------------------

# (profile key, predicate that the signal is PRESENT)
SIGNAL_PREDICATES: dict[str, tuple[str, Callable[[Any], bool]]] = {
    "vulnerabilities": ("vulnerability_count", lambda v: isinstance(v, (int, float)) and v > 0),
    "critical": ("critical_vulnerability_count", lambda v: isinstance(v, (int, float)) and v > 0),
    "rdp": ("exposed_rdp", lambda v: bool(v)),
    "database": ("exposed_database", lambda v: bool(v)),
    "exchange": ("exposed_exchange", lambda v: bool(v)),
    "eol": ("eol_product_count", lambda v: isinstance(v, (int, float)) and v > 0),
}

SIGNAL_TERMS: dict[str, list[str]] = {
    "vulnerabilities": ["vulnerab"],
    "critical": ["critical"],
    "rdp": ["rdp", "remote desktop"],
    "database": ["database"],
    "exchange": ["exchange"],
    "eol": ["end-of-life", "end of life", "eol"],
}

# Assertive breach/compromise claims are a fabrication in outreach. A negated
# or hypothetical mention ("not evidence of a breach", "spotted a suspicious
# service") is not. The product prompt tells the model to say "not evidence of
# a breach", so the check must only strike assertive phrasing.
FABRICATION_TERMS = (
    "has been breached",
    "was breached",
    "were breached",
    "were compromised",
    "was compromised",
    "is compromised",
    "detected a breach",
    "detected a compromise",
    "confirmed breach",
    "suffered a breach",
    "experienced a breach",
    "ransomware",
    "hacked",
    "pwned",
)

# Un-filled template placeholders are a contact/personalisation fabrication.
PLACEHOLDER_RE = re.compile(r"\{\{|\}\}|\[[A-Za-z][A-Za-z0-9 ]*\]")

# A low-friction call to action: an invitation or a direct question.
CTA_TERMS = ("?", "discuss", "open to", "let us know", "conversation", "would you like", "feel free", "call", "chat")

OUTREACH_MAX_WORDS = 150
SUMMARY_MAX_WORDS = 120  # the company-summary prompt's explicit limit

# A term preceded by one of these in the same sentence is negated, so it is not
# an invented-signal claim ("no critical vulnerabilities were detected").
NEGATION_TERMS = ("no ", "no\n", "not ", "nor ", "without", "no known", "none ")

CONTENT_FEATURES = ("outreach", "company_summary")


def normalize(text: str) -> str:
    # Unicode hyphens/dashes used by word-wrapped editors and LLM output should
    # not defeat "end-of-life" style matches.
    for char in ("\u2010", "\u2011", "\u2012", "\u2013", "\u2014"):
        text = text.replace(char, "-")
    return text.lower()


def _positions(low_text: str, term: str) -> list[int]:
    if len(term) <= 3:
        return [match.start() for match in re.finditer(r"\b" + re.escape(term) + r"\b", low_text)]
    positions: list[int] = []
    start = 0
    while True:
        found = low_text.find(term, start)
        if found == -1:
            break
        positions.append(found)
        start = found + 1
    return positions


def is_negated(low_text: str, position: int) -> bool:
    """Negation applies until the previous sentence, clause, or line boundary."""
    start = 0
    for boundary in (".", "!", "?", ";", ",", "\n"):
        marker = low_text.rfind(boundary, 0, position)
        if marker > start:
            start = marker + 1
    context = low_text[start:position]
    return any(neg in context for neg in NEGATION_TERMS)


def mentions(low_text: str, term: str) -> bool:
    """Return True when term appears at least once without a nearby negation."""
    return any(not is_negated(low_text, pos) for pos in _positions(low_text, term))


def present_signals(company: dict) -> list[str]:
    return [name for name, (key, pred) in SIGNAL_PREDICATES.items() if pred(company.get(key))]


def absent_signals(company: dict) -> list[str]:
    return [name for name, (key, pred) in SIGNAL_PREDICATES.items() if not pred(company.get(key))]


def evaluate_content(feature: str, content: str, company: dict) -> tuple[dict, dict]:
    """Return (criteria_results, notes) for one generated content output."""
    text = content or ""
    low = normalize(text)
    present = present_signals(company)
    absent = absent_signals(company)

    covers_signal: bool | None = None
    if present:
        covers_signal = any(
            mentions(low, term) for name in present for term in SIGNAL_TERMS[name]
        )

    no_invented_signal = not any(
        mentions(low, term) for name in absent for term in SIGNAL_TERMS[name]
    )

    no_fabrication = not any(term in low for term in FABRICATION_TERMS) and not PLACEHOLDER_RE.search(text)

    results: dict[str, Any] = {
        "covers_signal": covers_signal,
        "no_invented_signal": no_invented_signal,
        "no_fabrication": no_fabrication,
    }
    if feature == "outreach":
        results["has_subject"] = "subject:" in low
        results["word_count_ok"] = word_count(text) <= OUTREACH_MAX_WORDS
        results["has_cta"] = any(term in low for term in CTA_TERMS)
    else:
        results["word_count_ok"] = word_count(text) <= SUMMARY_MAX_WORDS

    notes = {
        "words": word_count(text),
        "present_signals": present,
        "absent_signals": absent,
        "applies": [name for name, value in results.items() if value is not None],
    }
    return results, notes


def clean_pass(results: dict) -> bool:
    applicable = [value for value in results.values() if value is not None]
    return bool(applicable) and all(applicable)


def word_count(text: str) -> int:
    if not text:
        return 0
    # Subject line "Subject: ..." and signatures are part of the message.
    return len(re.findall(r"\S+", text))


def validate_classification(response: dict) -> list[str]:
    """Schema + decision sanity checks for account_scoring trace rows."""
    violations: list[str] = []
    if not isinstance(response.get("ai_score"), int) or not 0 <= response["ai_score"] <= 100:
        violations.append("ai_score out of range")
    if response.get("priority") not in {"HIGH", "MEDIUM", "LOW"}:
        violations.append("priority not an enum value")
    confidence = response.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        violations.append("confidence out of range")
    if not response.get("reasoning"):
        violations.append("empty reasoning")
    return violations


# ---------------------------------------------------------------------------
# Trace-file run: score every successful content row in the JSONL trace sink.
# ---------------------------------------------------------------------------


def load_trace_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fetch_storage_trace_rows(storage_url: str, service_role_key: str, bucket: str, prefix: str = "traces/", timeout: float = 15.0) -> list[dict]:
    """Download trace records stored by SupabaseStorageTraceSink from a bucket.

    Each object is one JSONL record at ``traces/<prompt>/<year>/<month>/<day>/...``;
    mopping up the prefix and concatenating the records yields the JSONL stream.
    """
    import urllib.request

    base = storage_url.rstrip("/")
    headers = {"Authorization": f"Bearer {service_role_key}", "Content-Type": "application/json"}
    list_body = json.dumps({"prefix": prefix, "limit": 1000, "offset": 0, "sortBy": {"column": "name", "order": "asc"}}).encode("utf-8")
    list_request = urllib.request.Request(f"{base}/storage/v1/object/list/{bucket}", data=list_body, method="POST", headers=headers)
    with urllib.request.urlopen(list_request, timeout=timeout) as response:
        objects = json.loads(response.read().decode("utf-8"))

    rows: list[dict] = []
    names = sorted(obj.get("name", "") for obj in objects if obj.get("name", "").endswith(".json"))
    for name in names:
        request = urllib.request.Request(f"{base}/storage/v1/object/{bucket}/{name}", method="GET", headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
        for line in body.splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def run_traces(rows: list[dict], source: str = "") -> dict:
    content_rows, classification_rows = [], []
    for row in rows:
        if row.get("status") != "success":  # failures are already recorded in the line
            continue
        response = row.get("response") or {}
        if row.get("feature") in CONTENT_FEATURES and isinstance(response, dict) and response.get("content"):
            content_rows.append(row)
        elif row.get("feature") == "account_scoring" and isinstance(response, dict):
            classification_rows.append(row)

    by_feature: dict[str, dict] = {}
    scored_rows: list[dict] = []
    for row in content_rows:
        feature = row["feature"]
        company = (row.get("request") or {}).get("company") or {}
        criteria, notes = evaluate_content(feature, str(row["response"].get("content")), company)
        by_feature.setdefault(feature, {"n": 0, "criteria": {}, "clean": []})
        bucket = by_feature[feature]
        bucket["n"] += 1
        for name, value in criteria.items():
            if value is None:
                continue
            bucket["criteria"].setdefault(name, {"total": 0, "pass": 0, "failed_ids": []})
            bucket["criteria"][name]["total"] += 1
            if value:
                bucket["criteria"][name]["pass"] += 1
            else:
                bucket["criteria"][name]["failed_ids"].append(row["trace_id"])
        passed = clean_pass(criteria)
        bucket["clean"].append(passed)
        scored_rows.append(
            {
                "trace_id": row["trace_id"],
                "feature": feature,
                "prompt_version": row.get("prompt_version"),
                "clean_pass": passed,
                "criteria": {k: v for k, v in criteria.items()},
                "notes": notes,
            }
        )

    report_by_feature: dict[str, dict] = {}
    for feature, bucket in by_feature.items():
        criteria_report = {
            name: {
                "pass_rate": round(stat["pass"] / stat["total"], 3),
                "fail_trace_ids": stat["failed_ids"],
            }
            for name, stat in bucket["criteria"].items()
        }
        report_by_feature[feature] = {
            "n": bucket["n"],
            "pass_rates": criteria_report,
            "clean_pass_rate": round(sum(bucket["clean"]) / len(bucket["clean"]), 3),
        }

    classification_report = {
        "n": len(classification_rows),
        "valid": sum(1 for r in classification_rows if not validate_classification(r["response"])),
    }

    return {
        "source": source or "traces",
        "run_at": datetime.now(timezone.utc).isoformat(),
        "traces_total": len(rows),
        "traces_success": len(rows) - sum(1 for r in rows if r.get("status") != "success"),
        "content_rows_evaluated": len(content_rows),
        "classification_rows_validated": classification_report,
        "by_feature": report_by_feature,
        "rows": scored_rows,
    }


# ---------------------------------------------------------------------------
# Golden-set run: verify the rubric against hand-labelled cases and report
# per-criterion precision / recall / accuracy, plus clean-pass accuracy.
# ---------------------------------------------------------------------------


def load_cases(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def run_golden(cases: Iterable[dict]) -> dict:
    per_criterion: dict[str, dict] = {}
    correct_clean = 0
    total_clean = 0
    mislabeled: list[dict] = []

    for case in cases:
        predicted, notes = evaluate_content(
            case["feature"], case["content"], case.get("company") or {}
        )
        expected = case.get("expected") or {}
        passed = clean_pass(predicted)
        expected_clean = clean_pass({k: v for k, v in expected.items()})
        total_clean += 1
        if passed == expected_clean:
            correct_clean += 1
        else:
            mislabeled.append(
                {"company_id": case["company_id"], "expected_clean": expected_clean, "predicted_clean": passed}
            )

        for name, expected_value in expected.items():
            if expected_value is None:
                continue
            predicted_value = predicted.get(name)
            if predicted_value is None:
                continue
            bucket = per_criterion.setdefault(name, {"tp": 0, "fp": 0, "tn": 0, "fn": 0})
            if expected_value:
                if predicted_value:
                    bucket["tp"] += 1
                else:
                    bucket["fn"] += 1
            else:
                if predicted_value:
                    bucket["fp"] += 1
                else:
                    bucket["tn"] += 1

    criteria_report: dict[str, dict] = {}
    for name, c in per_criterion.items():
        total = c["tp"] + c["fp"] + c["tn"] + c["fn"]
        precision = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else 0.0
        recall = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else 0.0
        accuracy = (c["tp"] + c["tn"]) / total if total else 0.0
        criteria_report[name] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "accuracy": round(accuracy, 3),
            "tp": c["tp"],
            "fp": c["fp"],
            "tn": c["tn"],
            "fn": c["fn"],
        }

    return {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "cases": total_clean,
        "clean_pass_accuracy": round(correct_clean / total_clean, 3) if total_clean else None,
        "per_criterion": criteria_report,
        "mislabeled": mislabeled,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate generated LLM output against an evidence rubric")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--traces", type=Path, help="Score content rows from a JSONL LLM trace file")
    source.add_argument("--storage", action="store_true", help="Score content rows from a Supabase Storage bucket")
    source.add_argument("--golden", action="store_true", help="Check the rubric against hand-labelled cases")
    parser.add_argument("--cases", type=Path, default=Path("evals/datasets/output_rubric.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--storage-url", help="Supabase project URL (SUPABASE_URL)")
    parser.add_argument("--storage-key", help="Service-role key (SUPABASE_SERVICE_ROLE_KEY)")
    parser.add_argument("--bucket", default="llm-traces", help="Supabase Storage bucket holding trace objects (LLM_TRACE_BUCKET)")
    parser.add_argument("--trace-prefix", default="traces/", help="Object prefix, default traces/")
    args = parser.parse_args()

    if args.traces:
        result = run_traces(load_trace_rows(args.traces), source=str(args.traces))
    elif args.storage:
        storage_url = args.storage_url or os.getenv("SUPABASE_URL", "")
        storage_key = args.storage_key or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not (storage_url and storage_key):
            parser.error("--storage requires --storage-url/--storage-key (or SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY)")
        rows = fetch_storage_trace_rows(storage_url, storage_key, args.bucket, args.trace_prefix)
        result = run_traces(rows, source=f"storage://{args.bucket}/{args.trace_prefix}")
    else:
        result = run_golden(load_cases(args.cases))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()