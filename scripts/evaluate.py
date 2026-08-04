from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate EduAgent Hub against JSONL cases")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--workspace-id", default="demo")
    return parser.parse_args()


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at line {line_number}: {exc}") from exc
        cases.append(case)
    return cases


async def evaluate(args: argparse.Namespace) -> None:
    cases = load_cases(args.dataset)
    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    latencies: list[float] = []
    keyword_hits = 0
    citation_hits = 0
    details: list[dict[str, Any]] = []

    async with httpx.AsyncClient(base_url=args.base_url, headers=headers, timeout=90) as client:
        for index, case in enumerate(cases, start=1):
            started = time.perf_counter()
            response = await client.post(
                "/v1/chat",
                json={
                    "message": case["question"],
                    "session_id": f"evaluation-{index}",
                    "workspace_id": args.workspace_id,
                },
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            response.raise_for_status()
            payload = response.json()
            answer = payload["answer"].lower()
            expected = [str(item).lower() for item in case.get("expected_keywords", [])]
            hit = all(keyword in answer for keyword in expected) if expected else True
            citation_hit = bool(payload.get("citations"))

            keyword_hits += int(hit)
            citation_hits += int(citation_hit)
            latencies.append(elapsed_ms)
            details.append(
                {
                    "question": case["question"],
                    "keyword_hit": hit,
                    "citation_hit": citation_hit,
                    "latency_ms": round(elapsed_ms, 2),
                }
            )

    total = len(cases) or 1
    sorted_latencies = sorted(latencies)
    p95_index = max(0, min(len(sorted_latencies) - 1, round(len(sorted_latencies) * 0.95) - 1))
    summary = {
        "cases": len(cases),
        "keyword_recall": keyword_hits / total,
        "citation_rate": citation_hits / total,
        "latency_ms_mean": statistics.fmean(latencies) if latencies else 0.0,
        "latency_ms_p95": sorted_latencies[p95_index] if sorted_latencies else 0.0,
        "details": details,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(evaluate(parse_args()))
