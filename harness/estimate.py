#!/usr/bin/env python3
"""
estimate.py — Estimate the cost of a Claude API call across tiers, before you spend.

No API key required. Token counts are approximated offline (~4 chars/token).

Usage
-----
    python estimate.py "Summarize this email: ..."
    python estimate.py --input-tokens 50000 --output-tokens 2000
    python estimate.py "..." --cache-hit-ratio 0.8
    python estimate.py "..." --batch
    python estimate.py "..." --volume 10000
    python estimate.py --prompt-file my_prompt.txt
    cat my_prompt.txt | python estimate.py -
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from run_harness import cost_for, estimate_tokens, load_prices  # noqa: E402


def _read_prompt(args: argparse.Namespace) -> str | None:
    if args.prompt and args.prompt != "-":
        return args.prompt
    if args.prompt == "-":
        return sys.stdin.read()
    if args.prompt_file:
        return Path(args.prompt_file).read_text()
    return None


def _format_cost(c: float) -> str:
    if c < 0.01:
        return f"${c*100:.3f}¢"
    if c < 1.0:
        return f"${c:.4f}"
    return f"${c:,.2f}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt", nargs="?")
    p.add_argument("--prompt-file")
    p.add_argument("--input-tokens", type=int)
    p.add_argument("--output-tokens", type=int, default=500)
    p.add_argument("--cache-hit-ratio", type=float, default=0.0)
    p.add_argument("--batch", action="store_true")
    p.add_argument("--volume", type=int, default=1)
    args = p.parse_args()

    if args.input_tokens is not None:
        in_tok = args.input_tokens
        source = f"--input-tokens {in_tok}"
    else:
        prompt = _read_prompt(args)
        if not prompt:
            p.error("Provide a prompt, --prompt-file, or --input-tokens.")
        in_tok = estimate_tokens(prompt)
        source = f"{len(prompt):,} chars  (≈{in_tok:,} tokens, est.)"

    out_tok = args.output_tokens
    volume = max(1, args.volume)
    prices = load_prices()

    print(f"\nPrompt: {source}")
    print(f"Output: ~{out_tok:,} tokens")
    if args.cache_hit_ratio > 0:
        print(f"Cache:  {args.cache_hit_ratio:.0%} of input from cache hits (0.1x base input)")
    if args.batch:
        print(f"Batch:  Batch API pricing (50% off input + output)")
    if volume > 1:
        print(f"Volume: ×{volume:,} calls")
    print()

    print(f"{'Tier':<8} {'$/call':>14} {'$/1k calls':>16} {'Total':>16}")
    print("-" * 56)
    for tier in ("haiku", "sonnet", "opus"):
        c = cost_for(in_tok, out_tok, prices[tier],
                     cache_hit_ratio=args.cache_hit_ratio, batch=args.batch)
        per_k = c * 1000
        total = c * volume
        print(f"{tier:<8} {_format_cost(c):>14} {_format_cost(per_k):>16} "
              f"{_format_cost(total):>16}")

    if args.cache_hit_ratio > 0 or args.batch:
        print(f"\nBaseline (no cache, no batch) for comparison:")
        print(f"{'Tier':<8} {'$/call':>14} {'savings':>16}")
        print("-" * 40)
        for tier in ("haiku", "sonnet", "opus"):
            base = cost_for(in_tok, out_tok, prices[tier])
            mod  = cost_for(in_tok, out_tok, prices[tier],
                            cache_hit_ratio=args.cache_hit_ratio, batch=args.batch)
            saved = (base - mod) / base if base else 0
            print(f"{tier:<8} {_format_cost(base):>14} {saved:>15.0%}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
