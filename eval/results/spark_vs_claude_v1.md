# Spark-X2.6 vs. Claude — v1

**Date:** 2026-10-23/24. **Question:** can `spark-x2.6` (iFlytek, free 1B tokens, Anthropic-compatible endpoint) replace Claude for every runtime role for the next month?
**Answer: no.** Claude wins on every measured role except claim extraction, where they tie. The largest gaps are prose quality and following the world-state schema.

## Setup

- **Spark:**
  - `config/models_spark.yaml`: every role is `spark-x2.6`, with thinking off, `retries: 3`, `max_turns: 60`, and `timeout_s: 600`.
  - The Claude Agent SDK runs unchanged, with a per-role `base_url` (S1).
- **Claude:** the existing artifacts on the same inputs:
  - baseline suite `runs/suites/b514cd13600b4cabdbf2507fe7b8fe35.json`
  - simulation suite `runs/suites/edfd36f5af5f302e79247c9a2c34d705.json`
  - `world_v1.md`
  - the 4.3 and 4.4 runs
- **Thinking:** the Claude Code CLI omits the `thinking` parameter when thinking is disabled, and Spark then thinks by default. That made it about 5× slower; extraction took 4 min 07 s instead of 44 s. Sending `CLAUDE_CODE_EXTRA_BODY={"thinking":{"type":"disabled"}}` fixes it. All the numbers below are with thinking off.
- **Spark tokens:** about 110M, of which 103M were cache reads, over 80 runs. Claude spend: none (only `spark-x2.6` was called, at the author's instruction).
- **Code added along the way, all general and opt-in per role:**
  - per-role `base_url`, `retries`, `max_turns`, and `timeout_s`
  - reference-error messages that name the offending values
  - a cost cap that counts only billed providers
  - tolerant reading of old run metadata

## Results by role

| Role | Measure | Claude | Spark |
|---|---|---|---|
| **Baseline writer** | Blind pairwise, Codex `gpt-6.1-sol` high, both orders, 9 pairs | **18/18 judgments**, every axis | 0/18 |
| | Usable stories / in 2,000-3,000 words | 10/10 / 7/10 | 9/10 (one 29-word non-story) / 3/10 (29-6,120 words) |
| | Median time per story | 213 s | 344 s |
| **Initializer** | Worlds created (simulation suite) | 10/10 | 1/10 with 1 retry; 2/10 with 3 retries and value-naming errors |
| **Simulation, day 1** | Day completes + story (suite) | 8/10 | 1/10 (initializer blocks the rest) |
| **Simulation, day 2** (Spark on copies of Claude's 9 day-1 worlds) | Day completes | — (Claude's 3-day world: 3/3 days) | 7/9. 2 failed: invalid character structured output, a plan over 140 characters |
| | Story written | — | 4/9. 3 failed narrator grounding (cites events outside the act) |
| | Wall time per day | about 10-15 min | 43-104 min |
| | Overdue situations (code) | 0 in 10/10 world-days | 4 in 1 world (`904577-spark`) |
| **Claim extraction (4.3)** | Type accuracy, test set | 96.2% (1 run each, off and adaptive) | **96.2% in 5/5 runs** (same miss, #23) |
| **Verdicts (4.4)**, planted story | Runs that complete | 1/3 (evidence check) | 0/5 (4 evidence fabrications, 1 timeout) |
| | Plants caught, when complete | 3/3 | — |
| **World judge** | Finished | 10/10 | 8/10 (2 timeouts at 600 s) |
| | Required catches (W1 test) | hikari_ochette_1 outcomes 22, 28, 29; Throné 235 | 22, 28, 29, **37**; Throné 235 |
| | Canon catches | La'mani revived (agnea_throne_1) | Missed La'mani; duplicate findings |

Runs:
- Spark baseline suite: `runs/suites/488983c8a6bef8b973d3b7d2c3b08ccb.json`
- Spark simulation suites: `runs/suites/d48825412eb427a8d218572d2b938133.json` (1 retry) and `runs/suites/3434c56865bc857bf19e0b0686ec889c.json` (3 retries)
- Day-2 worlds: `worlds/<claude world id>-spark`
- Spark judge on Claude worlds: `runs/20261023-122222-7c8210` … `20261023-130040-0f127b`
- Spark judge on Spark day 2: `runs/20261023-170742-3ad4af` … `20261023-173128-3d6664`

## Why the blind judge preferred Claude (from its reasons)

- **Lore and scope:**
  - Spark brought back defeated enemies (a Duorduor as a "neighbor").
  - It misread relationships: Joe is treated as someone Partitio needs help recognizing.
  - It misstated Ochette's mission with Tera.
- **Voice:** both characters give long, similar philosophical speeches.
- **Structure:** repetitive reflection instead of an episode; length not respected.

## Failure patterns specific to Spark

1. **Reference fields in structured output.** Spark puts main characters into `people`, writes "Castti" in `touches`, and invents place slugs. It repeats the same error after being told the exact offending value.
2. **Grounding citations.** The narrator cites events outside its act, and the validator quotes KB text that isn't in the file.
3. **Calls that stall.** There were 3 hangs of 10 minutes or more across the judge and validator, before `timeout_s` was added.
4. **Weak built-in OT2 knowledge.** Asked directly, it names OT1 characters as OT2 travelers, so it depends on the KB more than Claude does.

## Recommendation

- **Don't switch the runtime to Spark.** Every story-producing role loses clearly, and the world engine can't initialize reliably.
- **Spark is good enough for claim extraction.** It matches Claude, is stable over 5 runs, and costs nothing. It's a candidate for that one call, if mixing providers is acceptable.
- **The 4.4 evidence check fails for both models.** Requiring verbatim quotes trips Claude 2/3 of the time and Spark 5/5. It needs a design decision: either mark the claim unverified, or fail the run.
