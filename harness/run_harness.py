#!/usr/bin/env python3
"""
run_harness.py — Token + cost harness for the model-cost-advisor skill.

For each case in eval_cases.yaml, sends the prompt to a configurable set of
Claude models, records input + output token counts and dollar cost, and prints
a per-case comparison plus aggregate totals. Supports --runs N for variance,
--cache-hit-ratio and --batch for optimization modifiers.

Usage
-----
    export ANTHROPIC_API_KEY=sk-ant-...
    pip install -r requirements.txt
    python run_harness.py --runs 3
    python run_harness.py --dry-run
    python run_harness.py --models haiku sonnet
    python run_harness.py --cache-hit-ratio 0.8 --batch

Pricing is read from prices.json. Verify against current Anthropic docs.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.stderr.write("Missing dependency: pyyaml. Run `pip install -r requirements.txt`.\n")
    sys.exit(1)


HERE = Path(__file__).parent
CASES_PATH = HERE / "eval_cases.yaml"
PRICES_PATH = HERE / "prices.json"
RESULTS_CSV = HERE / "results.csv"
SUMMARY_JSON = HERE / "summary.json"


MODEL_ALIASES: dict[str, str] = {
    "haiku":  "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus":   "claude-opus-4-6",
}


def load_prices() -> dict[str, dict[str, float]]:
    if PRICES_PATH.exists():
        return json.loads(PRICES_PATH.read_text())
    return {
        "haiku":  {"input_per_mtok": 1.00, "output_per_mtok": 5.00},
        "sonnet": {"input_per_mtok": 3.00, "output_per_mtok": 15.00},
        "opus":   {"input_per_mtok": 5.00, "output_per_mtok": 25.00},
    }


@dataclass
class CaseResult:
    case_id: str
    model: str
    run: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    error: str = ""


@dataclass
class CaseSummary:
    case_id: str
    model: str
    n: int
    mean_input: float
    mean_output: float
    mean_cost: float
    stdev_cost: float
    min_cost: float
    max_cost: float
    mean_latency_ms: float


# Stackable Anthropic pricing modifiers.
CACHE_HIT_MULTIPLIER = 0.1
BATCH_MULTIPLIER     = 0.5


def cost_for(
    input_tokens: int,
    output_tokens: int,
    prices: dict[str, float],
    *,
    cache_hit_ratio: float = 0.0,
    batch: bool = False,
) -> float:
    cache_hit_ratio = max(0.0, min(1.0, cache_hit_ratio))
    uncached_in = input_tokens * (1 - cache_hit_ratio)
    cached_in   = input_tokens * cache_hit_ratio

    input_cost  = (
        (uncached_in / 1_000_000) * prices["input_per_mtok"] +
        (cached_in   / 1_000_000) * prices["input_per_mtok"] * CACHE_HIT_MULTIPLIER
    )
    output_cost = (output_tokens / 1_000_000) * prices["output_per_mtok"]

    if batch:
        input_cost  *= BATCH_MULTIPLIER
        output_cost *= BATCH_MULTIPLIER

    return input_cost + output_cost


def call_model(model_full_name: str, prompt: str, max_tokens: int = 1024) -> tuple[int, int, int, str]:
    try:
        from anthropic import Anthropic
    except ImportError:
        return 0, 0, 0, "anthropic SDK not installed"

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return 0, 0, 0, "ANTHROPIC_API_KEY not set"

    client = Anthropic()
    t0 = time.time()
    try:
        resp = client.messages.create(
            model=model_full_name,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        return 0, 0, int((time.time() - t0) * 1000), f"{type(e).__name__}: {e}"

    latency_ms = int((time.time() - t0) * 1000)
    return resp.usage.input_tokens, resp.usage.output_tokens, latency_ms, ""


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def run(cases: list[dict[str, Any]], models: list[str], runs: int, dry_run: bool,
        prices: dict[str, dict[str, float]],
        cache_hit_ratio: float = 0.0,
        batch: bool = False) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        for model_alias in models:
            model_full = MODEL_ALIASES[model_alias]
            model_prices = prices[model_alias]
            for run_idx in range(1, runs + 1):
                if dry_run:
                    in_tok  = estimate_tokens(case["prompt"])
                    out_tok = 256
                    latency = 0
                    err = "dry-run"
                else:
                    in_tok, out_tok, latency, err = call_model(model_full, case["prompt"])
                results.append(CaseResult(
                    case_id=case["id"],
                    model=model_alias,
                    run=run_idx,
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cost_usd=cost_for(in_tok, out_tok, model_prices,
                                      cache_hit_ratio=cache_hit_ratio, batch=batch),
                    latency_ms=latency,
                    error=err,
                ))
    return results


def summarize(results: list[CaseResult]) -> list[CaseSummary]:
    by_key: dict[tuple[str, str], list[CaseResult]] = {}
    for r in results:
        by_key.setdefault((r.case_id, r.model), []).append(r)
    summaries: list[CaseSummary] = []
    for (case_id, model), runs_ in by_key.items():
        costs = [r.cost_usd for r in runs_]
        summaries.append(CaseSummary(
            case_id=case_id, model=model, n=len(runs_),
            mean_input=statistics.mean(r.input_tokens for r in runs_),
            mean_output=statistics.mean(r.output_tokens for r in runs_),
            mean_cost=statistics.mean(costs),
            stdev_cost=statistics.stdev(costs) if len(costs) > 1 else 0.0,
            min_cost=min(costs), max_cost=max(costs),
            mean_latency_ms=statistics.mean(r.latency_ms for r in runs_),
        ))
    return summaries


def print_table(summaries: list[CaseSummary]) -> None:
    by_case: dict[str, dict[str, CaseSummary]] = {}
    for s in summaries:
        by_case.setdefault(s.case_id, {})[s.model] = s
    header = f"{'case':<40} {'model':<8} {'in_tok':>8} {'out_tok':>8} {'$/run':>10} {'stdev':>8}"
    print(header)
    print("-" * len(header))
    for case_id, by_model in by_case.items():
        for model, s in by_model.items():
            print(f"{case_id:<40} {model:<8} {s.mean_input:>8.0f} {s.mean_output:>8.0f} "
                  f"{s.mean_cost:>10.5f} {s.stdev_cost:>8.5f}")
        if "haiku" in by_model and "opus" in by_model:
            mult = by_model["opus"].mean_cost / max(by_model["haiku"].mean_cost, 1e-9)
            print(f"{'  → opus/haiku cost ratio':<40} {'':<8} {'':>8} {'':>8} {mult:>10.1f}x")
        print()


def write_outputs(results: list[CaseResult], summaries: list[CaseSummary]) -> None:
    with RESULTS_CSV.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))
    SUMMARY_JSON.write_text(json.dumps([asdict(s) for s in summaries], indent=2))
    print(f"\nWrote {RESULTS_CSV.name} and {SUMMARY_JSON.name}")


def main() -> int:
    p = argparse.ArgumentParser(description="Token + cost harness for model-cost-advisor")
    p.add_argument("--runs", type=int, default=1)
    p.add_argument("--models", nargs="+", default=["haiku", "sonnet", "opus"],
                   choices=list(MODEL_ALIASES.keys()))
    p.add_argument("--cases", nargs="+")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--cache-hit-ratio", type=float, default=0.0,
                   help="Fraction of input tokens served from cache (0–1).")
    p.add_argument("--batch", action="store_true",
                   help="Apply Batch API pricing (50%% off).")
    args = p.parse_args()

    cases = yaml.safe_load(CASES_PATH.read_text())["cases"]
    if args.cases:
        cases = [c for c in cases if c["id"] in set(args.cases)]
        if not cases:
            print("No matching cases.", file=sys.stderr)
            return 2

    prices = load_prices()
    modifiers = []
    if args.cache_hit_ratio > 0:
        modifiers.append(f"cache={args.cache_hit_ratio:.0%}")
    if args.batch:
        modifiers.append("batch")
    mod_str = f"   Modifiers: {', '.join(modifiers)}" if modifiers else ""
    print(f"Models: {args.models}   Runs: {args.runs}   Cases: {len(cases)}   "
          f"Dry-run: {args.dry_run}{mod_str}\n")

    results = run(cases, args.models, args.runs, args.dry_run, prices,
                  cache_hit_ratio=args.cache_hit_ratio, batch=args.batch)
    summaries = summarize(results)
    print_table(summaries)
    write_outputs(results, summaries)
    total_cost = sum(r.cost_usd for r in results)
    print(f"\nTotal cost across all runs: ${total_cost:.4f}")
    if args.dry_run:
        print("(dry-run estimates — token counts are approximate)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
