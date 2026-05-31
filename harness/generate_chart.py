#!/usr/bin/env python3
"""
generate_chart.py — Emit an SVG of the missing-extractor savings curve.

No external plotting deps. Output: docs/savings-curve.svg
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from run_harness import load_prices  # noqa: E402
from failure_mode_test import (  # noqa: E402
    AVG_TOKENS_PER_DOC, N_AGREEMENTS,
    cost_extractor_path, cost_full_doc_path,
)


OUT = HERE.parent / "docs" / "savings-curve.svg"
FOLLOWUP_POINTS = [1, 2, 5, 10, 20, 50, 100, 200, 500]

W, H = 760, 440
MARGIN_L, MARGIN_R, MARGIN_T, MARGIN_B = 70, 30, 50, 60
PLOT_W = W - MARGIN_L - MARGIN_R
PLOT_H = H - MARGIN_T - MARGIN_B


def log10(x: float) -> float:
    return math.log10(max(x, 1e-9))


def x_of(followups: int, x_min_log: float, x_max_log: float) -> float:
    return MARGIN_L + (log10(followups) - x_min_log) / (x_max_log - x_min_log) * PLOT_W


def y_of(value: float, y_max: float) -> float:
    return MARGIN_T + PLOT_H - (value / y_max) * PLOT_H


def main() -> int:
    prices = load_prices()
    ratios = []
    for f in FOLLOWUP_POINTS:
        full = cost_full_doc_path("haiku", prices, f)
        extr = cost_extractor_path("haiku", prices, f)
        ratios.append(full / max(extr, 1e-9))

    y_max = math.ceil(max(ratios) / 5) * 5
    x_min_log = log10(min(FOLLOWUP_POINTS))
    x_max_log = log10(max(FOLLOWUP_POINTS))

    points = " ".join(
        f"{x_of(f, x_min_log, x_max_log):.1f},{y_of(r, y_max):.1f}"
        for f, r in zip(FOLLOWUP_POINTS, ratios)
    )

    y_ticks = list(range(0, int(y_max) + 1, 5))
    x_ticks = FOLLOWUP_POINTS

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif" '
        f'font-size="13">',
        f'<rect width="{W}" height="{H}" fill="white"/>',
        f'<text x="{W//2}" y="26" text-anchor="middle" font-size="17" font-weight="600">'
        'Cost savings from a structured extractor</text>',
        f'<text x="{W//2}" y="44" text-anchor="middle" fill="#666" font-size="12">'
        f'{N_AGREEMENTS:,} documents × {AVG_TOKENS_PER_DOC:,} tokens, '
        'Haiku rates · log-scale x-axis</text>',
    ]
    for yt in y_ticks:
        y = y_of(yt, y_max)
        svg.append(f'<line x1="{MARGIN_L}" y1="{y:.1f}" x2="{W-MARGIN_R}" y2="{y:.1f}" '
                   f'stroke="#eee" stroke-width="1"/>')
        svg.append(f'<text x="{MARGIN_L-8}" y="{y+4:.1f}" text-anchor="end" '
                   f'fill="#666">{yt}x</text>')
    for xt in x_ticks:
        x = x_of(xt, x_min_log, x_max_log)
        svg.append(f'<line x1="{x:.1f}" y1="{MARGIN_T+PLOT_H}" '
                   f'x2="{x:.1f}" y2="{MARGIN_T+PLOT_H+5}" stroke="#999"/>')
        svg.append(f'<text x="{x:.1f}" y="{MARGIN_T+PLOT_H+20}" text-anchor="middle" '
                   f'fill="#666">{xt}</text>')
    svg.append(f'<line x1="{MARGIN_L}" y1="{MARGIN_T+PLOT_H}" '
               f'x2="{W-MARGIN_R}" y2="{MARGIN_T+PLOT_H}" stroke="#333"/>')
    svg.append(f'<line x1="{MARGIN_L}" y1="{MARGIN_T}" '
               f'x2="{MARGIN_L}" y2="{MARGIN_T+PLOT_H}" stroke="#333"/>')
    svg.append(f'<polyline points="{points}" fill="none" '
               f'stroke="#0066cc" stroke-width="2.5"/>')
    for f, r in zip(FOLLOWUP_POINTS, ratios):
        x = x_of(f, x_min_log, x_max_log)
        y = y_of(r, y_max)
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#0066cc"/>')
        if f in (1, 5, 50, 500):
            svg.append(f'<text x="{x:.1f}" y="{y-10:.1f}" text-anchor="middle" '
                       f'fill="#0066cc" font-weight="600">{r:.1f}x</text>')
    svg.append(f'<text x="{W//2}" y="{H-15}" text-anchor="middle" fill="#333" '
               f'font-size="13">Follow-up queries over the corpus</text>')
    svg.append(f'<text x="20" y="{MARGIN_T+PLOT_H/2}" text-anchor="middle" '
               f'fill="#333" font-size="13" '
               f'transform="rotate(-90 20 {MARGIN_T+PLOT_H/2})">'
               'Cost ratio (full-doc / extract-once)</text>')
    svg.append('</svg>')

    OUT.parent.mkdir(parents=True, exist_ok=True)
    svg_text = "\n".join(svg)
    OUT.write_text(svg_text)
    print(f"Wrote {OUT.relative_to(HERE.parent)}  ({len(svg_text)} bytes)")
    print(f"Ratios: {dict(zip(FOLLOWUP_POINTS, [round(r,1) for r in ratios]))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
