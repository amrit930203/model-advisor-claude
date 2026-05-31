# Contributing

Thanks for the interest. Quick read — this is a small repo and the rules are short.

## Forking & attribution

Fork via GitHub's **Fork** button rather than copy-pasting the files. That keeps the lineage visible (forks show "forked from this repo" on GitHub) and makes future PRs easy. Copy-pasting and stripping attribution violates the MIT license — please don't.

If you build something cool on top of this, a link back is appreciated but not required.

## What kind of contributions land

**Welcome:**
- New eval cases in `harness/eval_cases.yaml` (especially negative controls — tasks where the skill should *not* nudge).
- New failure-pattern guardrails in `SKILL.md`, with a matching regression check in `harness/failure_mode_test.py`.
- Improvements to the cost math (e.g., support for new pricing modifiers like long-context tiers).
- Pricing updates in `prices.json` when Anthropic publishes new rates — include the verification date.
- Bug fixes, typos, clearer docs.

**Probably not:**
- Adding support for non-Claude providers. Scope is intentional.
- Renaming the skill or restructuring the layout without discussion.
- Removing the failure-mode regression test or its assertions.

If you're not sure, open an Issue before the PR.

## PR checklist

Before opening a PR:

1. **Run the regression test.** It must pass:
   ```bash
   python harness/failure_mode_test.py
   ```
2. **Run the dry-run sweep.** Confirms no case syntax errors:
   ```bash
   python harness/run_harness.py --dry-run
   ```
3. **If you touched the chart or trend math**, regenerate the chart:
   ```bash
   python harness/generate_chart.py
   ```
4. **If you changed prices**, update `_verified_at` in `prices.json`.
5. **Write a clear commit message.** What changed, and why.

CI runs the regression + dry-run on every PR. If CI is red, the PR won't be reviewed until it's green.

## Style

- Python: standard library where reasonable, minimal deps. Keep `requirements.txt` short.
- Markdown: prose over lists where it reads better. Use tables for data, not for everything.
- No marketing-speak. "10x faster" needs a number behind it.

## Reporting bugs

Open an Issue with:
- What you ran (exact command).
- What you expected.
- What actually happened (stack trace if any).
- Your Python version + OS.

Reproducible bugs get fixed faster than vague ones.

## Code of conduct

Be useful. Be specific. Disagree with reasoning, not with name-calling. If someone's being a jerk in an Issue or PR thread, flag it.

## License

By contributing, you agree your contribution is licensed under [MIT](LICENSE).
