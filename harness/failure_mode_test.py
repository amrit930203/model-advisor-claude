#!/usr/bin/env python3
"""
failure_mode_test.py — Regression test for the missing-extractor failure mode.

Asserts two things:
  1. COST DELTA: pulling N whole docs vs. querying a structured table produces
     a cost ratio above MIN_RATIO_AT_DEFAULT.
  2. SKILL BEHAVIOR: the SKILL.md text still names the failure pattern.

Run
---
    python failure_mode_test.py
    LIVE=1 python failure_mode_test.py     # also makes one Haiku API call
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from run_harness import MODEL_ALIASES, cost_for, load_prices, call_model  # noqa: E402


N_AGREEMENTS         = 1_000
AVG_TOKENS_PER_DOC   = 8_000
FIELDS_PER_DOC       = 6
TOKENS_PER_FIELD_ROW = 40

MIN_RATIO_AT_DEFAULT = 4
DEFAULT_FOLLOWUPS = 5
TREND_FOLLOWUPS   = [5, 50, 500]


def cost_full_doc_path(model: str, prices, followups: int) -> float:
    per_query_input  = N_AGREEMENTS * AVG_TOKENS_PER_DOC
    per_query_output = 2_000
    total = 0.0
    for _ in range(followups + 1):
        total += cost_for(per_query_input, per_query_output, prices[model])
    return total


def cost_extractor_path(model: str, prices, followups: int) -> float:
    extract_input  = N_AGREEMENTS * AVG_TOKENS_PER_DOC
    extract_output = N_AGREEMENTS * FIELDS_PER_DOC * 8
    table_size_tokens = N_AGREEMENTS * FIELDS_PER_DOC * TOKENS_PER_FIELD_ROW
    total = cost_for(extract_input, extract_output, prices[model])
    for _ in range(followups + 1):
        total += cost_for(table_size_tokens, 2_000, prices[model])
    return total


def check_cost_delta(prices) -> bool:
    print("\n[1/2] Cost-delta check at default load")
    print(f"      corpus: {N_AGREEMENTS:,} docs × {AVG_TOKENS_PER_DOC:,} tok, "
          f"{DEFAULT_FOLLOWUPS+1} queries")
    ok = True
    for model in ("haiku", "sonnet", "opus"):
        full = cost_full_doc_path(model, prices, DEFAULT_FOLLOWUPS)
        extr = cost_extractor_path(model, prices, DEFAULT_FOLLOWUPS)
        ratio = full / max(extr, 1e-9)
        status = "PASS" if ratio >= MIN_RATIO_AT_DEFAULT else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"      {model:<6}  full=${full:>10.2f}  extract=${extr:>10.2f}  "
              f"ratio={ratio:>6.1f}x  [{status}]")
    print(f"      (require ratio ≥ {MIN_RATIO_AT_DEFAULT}x at default load)")

    print("\n      Ratio vs. followups (Haiku, shows compounding savings):")
    print(f"      {'followups':>10} {'full ($)':>12} {'extract ($)':>14} {'ratio':>8}")
    for f in TREND_FOLLOWUPS:
        full = cost_full_doc_path("haiku", prices, f)
        extr = cost_extractor_path("haiku", prices, f)
        ratio = full / max(extr, 1e-9)
        print(f"      {f:>10} {full:>12.2f} {extr:>14.2f} {ratio:>7.1f}x")
    return ok


SKILL_PATH = HERE.parent / "SKILL.md"

REQUIRED_PHRASES = [
    "missing-extractor",
    "Context size is the token count itself",
    "Extract once, query many",
]


def check_skill_text() -> bool:
    print("\n[2/2] Skill-text structural check")
    if not SKILL_PATH.exists():
        print(f"      FAIL — {SKILL_PATH} not found")
        return False
    text = SKILL_PATH.read_text()
    ok = True
    for phrase in REQUIRED_PHRASES:
        present = phrase.lower() in text.lower()
        print(f"      {'PASS' if present else 'FAIL'}  contains: {phrase!r}")
        ok = ok and present
    return ok


def check_live_call() -> bool:
    if not os.environ.get("LIVE"):
        print("\n[live] Skipped (set LIVE=1 to enable a single live API call)")
        return True
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\n[live] LIVE=1 but ANTHROPIC_API_KEY not set — skipping")
        return True
    print("\n[live] One Haiku call to confirm SDK + auth work")
    in_tok, out_tok, latency, err = call_model(
        MODEL_ALIASES["haiku"], "Reply with the single word: ok", max_tokens=8,
    )
    if err:
        print(f"      FAIL — {err}")
        return False
    print(f"      PASS — in={in_tok} out={out_tok} latency={latency}ms")
    return True


def main() -> int:
    prices = load_prices()
    print("Missing-extractor failure-mode regression")
    print("=" * 60)
    ok = True
    ok &= check_cost_delta(prices)
    ok &= check_skill_text()
    ok &= check_live_call()
    print("\n" + ("ALL CHECKS PASSED" if ok else "REGRESSIONS DETECTED"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
