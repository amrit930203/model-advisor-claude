---
name: model-cost-advisor
description: Suggest a more cost-appropriate Claude model and catch common token-waste patterns before they ship a big bill. Trigger when (a) the task is routine, low-complexity, or high-volume (Q&A, summarization, formatting, extraction, translation, classification, short-message drafting, boilerplate code, repetitive/batch operations); (b) the user mentions API bills, token spend, or asks whether they're on the right model; (c) the planned approach would load many large source documents into context because no pre-extraction layer exists; or (d) the request matches a stray-waste pattern — "show me everything", retrying the same question after a bad answer, open-ended "keep refining" loops, implicit per-item batches in a single turn, default-verbose long-form requests, or recursive "elaborate on each point" expansions. Do NOT trigger for genuinely complex work (deep multi-step reasoning, system/architecture design, hard debugging, novel research, nuanced long-form writing).
---

# Model Cost Advisor

Help users avoid overpaying on Claude in two ways:
1. **Tier nudge** — flag when a premium model is being used for a task a cheaper tier would handle just as well.
2. **Context-bloat guardrail** — flag when the planned approach pulls whole source documents into the prompt because no structured extraction layer exists, which inflates input tokens far more than model choice does.

Always complete the task either way. Nudges are one short sentence, not a billing alert.

---

## Decision logic

Before answering any tool-using or generation task, run this check silently:

```
1. Estimate token shape:
   - input_tokens   ≈ prompt + retrieved context + any whole documents being loaded
   - output_tokens  ≈ requested completion length
   - call_volume    ≈ 1 (one-off) | N (batch over a corpus)

2. Classify task complexity (see tables below).

3. If complexity is LOW and the user appears on a premium tier → emit tier nudge.
4. If input_tokens balloon because whole documents are being loaded with no
   extractor → emit context-bloat nudge BEFORE the tier nudge. Tier savings are
   linear; context savings are often 10–100x.
5. Do the task.
```

The two nudges are independent. A high-volume extraction job over 10k contracts can warrant both: switch from Opus to Haiku *and* extract structured fields up front instead of shipping full PDFs.

---

## Tier nudge

### Tasks that usually DON'T need a premium model
Routine Q&A and factual lookups, summarization, paraphrasing, translation, grammar/spelling fixes, formatting and reformatting, simple data extraction or classification, short-message drafting, boilerplate or templated code, regex, simple SQL, repetitive/batch operations across many items.

### Tasks that DO justify a premium model — do NOT nudge
Deep multi-step reasoning, complex system/architecture design, hard or subtle debugging, novel research and analysis, nuanced long-form writing, ambiguous problems needing strong judgment, agentic workflows with many dependent steps.

### Picking the suggested tier — always name a specific model

Don't say "a cheaper tier" — pick one and name it. Use this lookup:

| Task shape | Suggested tier | Example tasks |
|---|---|---|
| Trivial / high-volume | **Haiku** | classification, extraction, regex, short rewrites, JSON formatting, simple Q&A, boilerplate code |
| Moderate but not complex | **Sonnet** | standard coding tasks, summarization with judgment, routine drafting, refactoring with constraints |
| Genuinely complex | **Opus** (no nudge) | architecture design, hard debugging, novel research, nuanced long-form writing, multi-step reasoning |
| Truly ambiguous between two | **"Haiku or Sonnet"** | name both, briefly say what tips it one way vs. the other, let the user pick |

### Tier-nudge templates (use the one that matches what you picked)

**When Haiku is the right pick** (trivial / high-volume):
> Haiku would handle this just as well — it's ~5x cheaper than Opus on input and ~5x cheaper on output, and the task is the kind it's tuned for. Happy to proceed either way:

**When Sonnet is the right pick** (moderate complexity):
> Sonnet is the right tier for this — Opus is overkill, but the task has enough judgment that Haiku might cut corners. Sonnet is ~3x cheaper than Opus. Happy to proceed either way:

**When it's genuinely ambiguous** (rare — don't reach for this if one tier clearly fits):
> Either Haiku or Sonnet would handle this without losing quality. Haiku if you care most about cost (~5x savings vs. Opus); Sonnet if you want a small accuracy buffer (~3x savings). Let me know, or I'll proceed on the current model:

Then answer immediately. Don't repeat the nudge in the same conversation unless the task type changes. Quote the rough cost multiple (5x, 3x) rather than specific dollar amounts — multiples stay accurate when pricing changes.

**Where to switch:**
- On the API → mention the `model` parameter and give the exact string (e.g. `model="claude-haiku-4-5-20251001"`).
- In the Claude app → mention the model picker in the message composer.
- In Claude Code → mention the `/model` slash command.

---

## Context-bloat guardrail (the bigger lever)

Model choice is a per-token multiplier. Context size is the token count itself. As of May 2026, Opus is only ~5x Haiku on input (down from 15x — Opus 4.5+ is priced at $5/$25 per Mtok). That makes the tier-switch argument weaker and the context-shape argument relatively more important. A 200-page document at 100k tokens dwarfs the cost of a 1-page summary regardless of model — bad retrieval patterns wipe out any tier savings.

Two other modifiers stack with model choice and often beat it:
- **Prompt caching** — cache reads are 0.1x base input. For repeated system prompts or corpus context, this is a 10x win without changing models.
- **Batch API** — 50% off both input and output for non-realtime workloads. Stacks with caching.

If the user is doing repetitive work over a stable corpus, mention caching/batching alongside any tier nudge.

### The missing-extractor anti-pattern
Trigger when the user asks Claude to:
- "Look through all the [agreements / contracts / tickets / emails / logs / reports / PDFs]" and
- there is no pre-existing extraction layer in the repo (no parsed fields, no embeddings index, no structured table, no per-document summary cache).

Default behavior in that situation is to load whole source documents into context, which means:
- input tokens scale with `N × avg_doc_size`,
- the same documents get re-loaded on every follow-up question,
- monthly token budget is consumed by raw text the model mostly ignores.

This shows up in many domains — contract review, support-ticket triage, log analysis, medical record search, email mining, compliance audits. The fix is the same regardless of domain.

### What to do instead — call this out before running the job
1. **Extract once, query many.** Pull the fields you actually need (parties, effective dates, renewal terms, signers, statuses, IDs) into a structured store. Then Claude reads the table, not the source.
2. **Index for retrieval.** If the questions are open-ended, build an embeddings index and pass top-k chunks instead of full docs.
3. **Cache summaries.** Pre-compute a short summary per document and load summaries into context; fall back to the full doc only when needed.
4. **Filter first.** Apply metadata filters (date range, status, owner) before any text hits the model.

### Context-bloat nudge template
> Before running this, a heads-up: pulling all the source documents into context every time will dominate your token spend — likely more than model choice does. If the repo doesn't already have a structured extractor or index, it's worth building one (parse the fields you actually need once, then have me query the table). Want me to scope that, or proceed with full-document loading for now?

Then proceed with whichever the user chooses.

---

## Stray patterns — other ways tokens leak

These are the high-frequency token-wasters that aren't tier choice and aren't whole-document loading. Each one has a short trigger and a one-line response. Pick the most relevant; never fire more than one stray-pattern nudge per turn.

Each stray-pattern nudge should name a specific tier when one obviously fits, the same way the tier nudge does. The pattern dictates what to suggest; the suggestion is concrete.

1. **Everything-dump.** Trigger: "show me / list / give me all the X" with no filter, no time range, no limit. Same family as context-bloat but worth catching even when no extractor is involved.
   > Heads-up: this will pull every X into context, which dominates the cost regardless of model. Want me to filter by date, status, or owner first? Once you have a filtered slice, **Haiku** is enough to read it back — no need to pay Opus rates for a list operation.

2. **Retry-on-failure.** Trigger: the same question was asked in the last few turns and Claude already gave an answer the user wasn't happy with. Just re-running on a bigger model rarely helps.
   > Before retrying — what specifically was wrong with the previous answer? Reshaping the prompt or adding context usually beats a tier bump. If the issue really is reasoning depth, go from Haiku→Sonnet or Sonnet→Opus *with* the diagnosis. Otherwise you're paying more for the same mistake.

3. **Infinite refinement.** Trigger: "keep iterating / refining / improving until it's perfect" with no stopping criterion.
   > Open-ended refinement compounds cost. I'll do 2 passes on **Sonnet** and stop unless you tell me a specific axis to keep improving on. (Sonnet rather than Opus because the first 2 passes usually catch 80% of the gain; reserve Opus for the polish round if you need one.)

4. **Implicit batch.** Trigger: "for each of these [N] items, do X" where N is in a single conversational turn.
   > This is N calls' worth of work happening in one turn. For N > ~100 it's cheaper to run as a real Batch API job (50% off) on **Haiku** than to do it inline on whatever model you're on. Want me to set that up, or proceed inline?

5. **Verbose-by-default.** Trigger: "give me a comprehensive / detailed / thorough analysis with examples" when the user hasn't said they need depth.
   > Long-form costs scale with output length. Want me to start with a 5-bullet version on **Sonnet** and expand only the parts you flag, or go straight to the full analysis? The bullets-first pattern usually saves >50% on output tokens.

6. **Recursive expansion.** Trigger: repeated "elaborate on each of those points" turns, where every answer gets expanded into more sub-answers that also get expanded.
   > Each expansion roughly doubles the context. Pick the 1–2 points you most want depth on — I'll do those on the current tier rather than expanding all of them. If you do want all of them expanded, **batching them once on Sonnet** is cheaper than doing them serially on Opus over multiple turns.

The point isn't to refuse any of these — it's to give the user a cheaper choice once, then proceed with whichever they pick.

## Self-signal footer

After firing any nudge (tier, context-bloat, or a stray pattern), Claude ends the response with a single-line footer so the user knows the skill triggered and which pattern caught it:

```
[cost-advisor: <pattern_name>]
```

For example: `[cost-advisor: tier-nudge]` or `[cost-advisor: stray/everything-dump]`. This is for the user's observability — they can grep their conversation history to see how often the skill is firing and on what. Don't add the footer when no nudge fired.

## What NOT to do
- Don't refuse or delay the task waiting for a decision.
- Don't nudge repeatedly or moralize about spend.
- Don't nudge when the premium model is clearly warranted.
- Don't fire more than one stray-pattern nudge per turn — pick the most relevant.
- Don't invent model names or prices — verify if quoting them.
- Don't bury the context-bloat warning at the end if the job is about to run on a large corpus — say it first.
- Don't add the self-signal footer on turns where no nudge fired.

---

## Harness

A test harness lives in `./harness/`. It runs eval cases across Haiku, Sonnet, and Opus, records input + output tokens and dollar cost per case, supports `--runs N` for variance, and includes a regression test for the missing-extractor failure mode.

Run it before shipping any change to this skill:

```
cd harness
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python run_harness.py --runs 3
python failure_mode_test.py
```

See `harness/README.md` for full instructions and how to add cases.
