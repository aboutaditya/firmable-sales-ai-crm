from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from sales_intelligence.ai.provider import OpenAICompatibleProvider


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def render_prompt(template: str, company: dict) -> str:
    return template.replace("{{company_profile}}", json.dumps(company, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run account-scoring cases through OpenRouter")
    parser.add_argument("--cases", type=Path, default=Path("evals/datasets/account_scoring.jsonl"))
    parser.add_argument("--prompt", type=Path, default=Path("backend/sales_intelligence/prompts/account_scoring/v1.txt"))
    parser.add_argument("--prompt-version", default=None)
    parser.add_argument("--output", type=Path, default=Path("evals/results/openrouter-predictions.jsonl"))
    parser.add_argument("--model", default=os.getenv("OPENROUTER_MODEL"))
    parser.add_argument("--api-key", default=os.getenv("OPENROUTER_API_KEY"))
    parser.add_argument("--base-url", default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip cases whose company_id already has a prediction in --output",
    )
    args = parser.parse_args()
    if not args.api_key:
        raise SystemExit("Set OPENROUTER_API_KEY or pass --api-key")
    if not args.model:
        raise SystemExit("Set OPENROUTER_MODEL or pass --model")

    provider = OpenAICompatibleProvider(
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "2")),
        input_cost_per_1k=_optional_float(os.getenv("OPENROUTER_INPUT_COST_PER_1K")),
        output_cost_per_1k=_optional_float(os.getenv("OPENROUTER_OUTPUT_COST_PER_1K")),
        http_referer=os.getenv("OPENROUTER_HTTP_REFERER", "http://localhost:3000"),
        app_title=os.getenv("OPENROUTER_APP_TITLE", "Sales Intelligence Evaluation"),
    )
    prompt = args.prompt.read_text(encoding="utf-8")
    prompt_version = args.prompt_version or args.prompt.stem
    args.output.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.resume and args.output.exists():
        for row in load_rows(args.output):
            done.add(row["company_id"])
    open_mode = "a" if args.resume and done else "w"
    pending = [case for case in load_rows(args.cases) if case["company_id"] not in done]
    with args.output.open(open_mode, encoding="utf-8") as stream:
        for case in pending:
            started = time.perf_counter()
            response = provider.qualify(case["company"], render_prompt(prompt, case["company"]))
            row = {
                "company_id": case["company_id"],
                "priority": response.result.priority,
                "ai_score": response.result.ai_score,
                "confidence": response.result.confidence,
                "reasoning": response.result.reasoning,
                "model": args.model,
                "prompt_version": prompt_version,
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
            }
            stream.write(json.dumps(row, sort_keys=True) + "\n")
            stream.flush()
            print(f"{case['company_id']}: {row['priority']} / {row['ai_score']}")
    print(f"Wrote predictions to {args.output}")


def _optional_float(value: str | None) -> float | None:
    return float(value) if value not in (None, "") else None


if __name__ == "__main__":
    main()
