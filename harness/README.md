# model-cost-advisor — Harness

This harness grades the `model-cost-advisor` skill on two axes:

1. **Token + cost behavior across tiers.** For every case in `eval_cases.yaml`, the harness runs the same prompt against Haiku, Sonnet, and Opus, records input + output tokens and dollar cost, and prints a side-by-side comparison. Use `--runs N` to repeat each case and surface variance.
2. **Failure-mode regression.** `failure_mode_test.py` asserts that the cost gap between "load all docs every query" and "extract once, query the table" stays large enough to justify the skill's existence, and that the SKILL.md text still names the failure pattern explicitly.

Both run offline by default (no API key required) for cheap CI use, and can be flipped to live mode when you actually want token counts from the API.

---

## Setup

```bash
cd harness
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...    # only needed for live runs
```

Pricing lives in `prices.json` so you can update rates without touching code. **Verify against current Anthropic pricing before relying on dollar figures.**

---

## Running

### Token + cost sweep
```bash
python run_harness.py                          # one run per case, all three tiers
python run_harness.py --runs 3                 # variance check
python run_harness.py --dry-run                # offline token estimate, no API calls
python run_harness.py --models haiku sonnet    # skip Opus
python run_harness.py --cases pull_all_agreements_no_extractor batch_extract_on_opus
python run_harness.py --cache-hit-ratio 0.8 --batch   # apply optimization modifiers
```

Outputs:
- stdout table with mean input/output tokens, $/run, stdev, and Opus/Haiku cost ratio
- `results.csv` — one row per (case, model, run)
- `summary.json` — aggregate stats per (case, model)

### Failure-mode regression
```bash
python failure_mode_test.py            # offline math + skill-text check
LIVE=1 python failure_mode_test.py     # also makes one Haiku call to confirm auth
```

Exits non-zero on regression — wire this into CI.

### Standalone cost estimator
```bash
python estimate.py "Summarize this email: ..."
python estimate.py --input-tokens 50000 --output-tokens 2000
python estimate.py "..." --cache-hit-ratio 0.8 --batch --volume 10000
```

No API key required.

### Generate the README chart
```bash
python generate_chart.py    # writes docs/savings-curve.svg
```

### Live benchmark report
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python run_benchmark.py     # writes BENCHMARK.md at repo root
```

---

## Adding a case

Append to `eval_cases.yaml`:

```yaml
- id: my_new_case
  prompt: |
    The exact user message to test.
  complexity: low | medium | high
  expect_nudge: tier | context_bloat | both | none
  suggested_tier: haiku | sonnet | opus
  notes: Why this case exists and what it's testing.
```

Cases should cover four buckets, in roughly this ratio:
- low-complexity / premium-overkill (tier nudge)
- moderate complexity (Sonnet target)
- genuinely complex (no nudge — negative control)
- missing-extractor / full-document-pull (context-bloat nudge)

Negative controls matter — they catch the skill becoming a billing nag.

---

## Interpreting the cost ratio

For the missing-extractor case, the more interesting number is in `failure_mode_test.py`: full-doc cost vs. structured-table cost. The ratio scales with usage — about 5x at 6 queries, climbing toward ~30x as followups grow. The test asserts ≥ 4x at the default load and prints a trend table so you can see compounding savings.

---

## Files

```
SKILL.md                  the skill itself (lives one level up)
harness/
  README.md               this file
  eval_cases.yaml         test cases
  prices.json             editable pricing
  requirements.txt        anthropic + pyyaml
  run_harness.py          token + cost sweep
  failure_mode_test.py    missing-extractor regression
  estimate.py             standalone CLI cost estimator
  generate_chart.py       writes the SVG embedded in README
  run_benchmark.py        writes the public BENCHMARK.md report
  results.csv             (gitignored) written by run_harness.py
  summary.json            (gitignored) written by run_harness.py
```
