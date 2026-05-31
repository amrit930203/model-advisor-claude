#!/usr/bin/env python3
"""
run_benchmark.py — Live harness run that produces a public BENCHMARK.md report.

Requires ANTHROPIC_API_KEY. Runs all cases × all tiers × 3 runs, writes a
timestamped markdown report at the repo root.

Usage
-----
    export ANTHROPIC_API_KEY=sk-ant-...
    python run_benchmark.py
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))

import yaml  # noqa: E402

from run_harness import MODEL_ALIASES, load_prices, run, summarize  # noqa: E402
from failure_mode_test import (  # noqa: E402
    AVG_TOKENS_PER_DOC, N_AGREEMENTS, TREND_FOLLOWUPS,
    cost_extractor_path, cost_full_doc_path,
)


def _git_sha() -> str:
    try:
        r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, check=True)
        return r.stdout.strip()
    except Exception:
        return "unknown"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |"]
    out.append("|" + "|".join(["---"] * len(headers)) + "|")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        return 2

    cases = yaml.safe_load((HERE / "eval_cases.yaml").read_text())["cases"]
    prices = load_prices()
    models = ["haiku", "sonnet", "opus"]
    runs_per_case = 3

    total_calls = len(cases) * len(models) * runs_per_case
    print(f"Running {len(cases)} cases × {len(models)} models × {runs_per_case} runs "
          f"= {total_calls} API calls...")
    print("This will spend real tokens. Ctrl-C to abort.\n")

    results = run(cases, models, runs_per_case, dry_run=False, prices=prices)
    summaries = summarize(results)

    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    sha = _git_sha()

    lines: list[str] = []
    lines.append("# Benchmark report")
    lines.append("")
    lines.append(f"**Generated:** {now}  •  **Commit:** `{sha}`  •  "
                 f"**Runs per case:** {runs_per_case}")
    lines.append("")
    lines.append("## Models tested")
    lines.append("")
    lines.append(_table(
        ["Alias", "Model ID", "Input $/MTok", "Output $/MTok"],
        [[m, MODEL_ALIASES[m], f"${prices[m]['input_per_mtok']:.2f}",
          f"${prices[m]['output_per_mtok']:.2f}"] for m in models],
    ))
    lines.append("")
    lines.append("## Per-case results")
    lines.append("")

    by_case: dict[str, dict] = {}
    for s in summaries:
        by_case.setdefault(s.case_id, {})[s.model] = s

    rows = []
    for case_id, by_model in by_case.items():
        for model in models:
            s = by_model.get(model)
            if not s:
                continue
            rows.append([
                f"`{case_id}`", model,
                f"{s.mean_input:,.0f}", f"{s.mean_output:,.0f}",
                f"${s.mean_cost:.5f}", f"±${s.stdev_cost:.5f}",
                f"{s.mean_latency_ms:,.0f}",
            ])
    lines.append(_table(
        ["Case", "Tier", "In tokens", "Out tokens", "$/run", "stdev", "ms"], rows,
    ))
    lines.append("")
    lines.append("## Missing-extractor failure mode")
    lines.append("")
    lines.append(f"Corpus: **{N_AGREEMENTS:,} docs × {AVG_TOKENS_PER_DOC:,} tokens** "
                 "each. Running on Haiku.")
    lines.append("")
    trend_rows = []
    for f in TREND_FOLLOWUPS:
        full = cost_full_doc_path("haiku", prices, f)
        extr = cost_extractor_path("haiku", prices, f)
        trend_rows.append([str(f), f"${full:,.2f}", f"${extr:,.2f}",
                           f"{full/max(extr, 1e-9):.1f}x"])
    lines.append(_table(
        ["Followups", "Full-doc path", "Extract-once path", "Savings"], trend_rows,
    ))
    lines.append("")

    total_cost = sum(r.cost_usd for r in results)
    lines.append("## Aggregate")
    lines.append("")
    lines.append(f"- Total API spend for this benchmark: **${total_cost:.4f}**")
    lines.append(f"- Total API calls: {len(results):,}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("Re-run with `python harness/run_benchmark.py`.")

    out_path = REPO / "BENCHMARK.md"
    out_path.write_text("\n".join(lines))
    print(f"\nWrote {out_path.relative_to(REPO)}")
    print(f"Total spend: ${total_cost:.4f}  ({len(results)} calls)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
