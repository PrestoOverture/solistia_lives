# World metrics v1 — baseline (roadmap W1)

**Date:** 2026-10-23. **Tool:** `story-engine eval world` (code: `src/story_engine/eval/world.py`, prompt: `prompts/world_judge.md`), judge role `world_judge` (Sonnet, effort high, thinking off).
**Inputs:** the 3.10 simulation suite (`runs/suites/edfd36f5af5f302e79247c9a2c34d705.json`, day 1 of each world) plus world `20261022-132251-067042` day 3. **Cost:** $2.26 for this run (r2), $2.44 for the discarded r1.

## Method

- **Code (data only, D27):**
  - completion: the world's clock reached day N+1 morning
  - overdue situations: status `open` with `due.day ≤ N`
  - counts
- **Judge:** one structured-output session per world-day. Its input is:
  - the end-of-day state
  - the day's events, scenes, and part-of-day outcomes
  - the previous day's events

  Each finding must cite evidence. Code checks the references:
  - event ids exist
  - `interactions_staged` cites only outcomes
  - no finding is left without a citation
  - no `continuity` on day 1
- **Only the latest simulated day is checkable.** `runs/<id>/world_before/` is re-copied before every tick (`simulation.run_day`), so it isn't a start-of-day snapshot. That is why `new_situations` (prd §6.6, "situations live and close") isn't measured yet.
- **r1 → r2:** In r1, 8 of 14 `interactions_staged` findings cited scene events or minor-only events, and 3 findings were "no violation" placeholders. The citation rules above were added (structure, not prompt rules), and r2 is the baseline.

## Results (r2)

| Case | World | Day | Run | Overdue | Outcomes | interactions_staged (findings) | state_follows_log | canon_and_scope | Cost |
|---|---|---|---|---|---|---|---|---|---|
| osvald_temenos_1 | `20261022-191741-6e0828` | 1 | `20261023-065530-73272e` | — | 1 | completion **false** (day failed: `new_people` named Temenos) | — | — | $0 |
| osvald_temenos_2 | `20261022-191742-92d71a` | 1 | `20261023-081116-a0eea1` | 0 | 2 | 1 | 1 | 3 | $0.21 |
| agnea_throne_1 | `20261022-191754-040be5` | 1 | `20261023-081208-29200d` | 0 | 4 | 4 | 2 | 1 | $0.20 |
| agnea_throne_2 | `20261022-191736-55a636` | 1 | `20261023-081304-f13f63` | 0 | 6 | 1 | 0 | 0 | $0.24 |
| hikari_ochette_1 | `20261022-191732-c0414f` | 1 | `20261023-081359-9b07c9` | 0 | 6 | 1 | 5 | 0 | $0.19 |
| hikari_ochette_2 | `20261022-192947-904577` | 1 | `20261023-081505-511e75` | 0 | 2 | 1 | 3 | 0 | $0.23 |
| castti_partitio_1 | `20261022-193554-adc7a7` | 1 | `20261023-081554-945c6c` | 0 | 3 | 1 | 2 | 0 | $0.20 |
| castti_partitio_2 | `20261022-193953-058a9a` | 1 | `20261023-081629-d4d868` | 0 | 1 | 1 | 3 | 1 | $0.22 |
| osvald_temenos_agnea_1 | `20261022-194405-16e997` | 1 | `20261023-081720-602c99` | 0 | 2 | 2 | 3 | 1 | $0.23 |
| osvald_temenos_agnea_2 | `20261022-194610-56e8c3` | 1 | `20261023-081810-4528c5` | 0 | 8 | 1 | 3 | 0 | $0.28 |
| (3-day world) | `20261022-132251-067042` | 3 | `20261023-081858-f21881` | 0 | 5 | 2 | 3 | 0 | $0.26 |

**Required catches (roadmap W1 Test):** both caught.
- hikari_ochette_1: outcomes 22, 28, and 29 were flagged. Outcome 37, a shared meal with the crew, was missed.
- World `20261022-132251-067042` day 3: event 235 vs. `characters.throne.where` was flagged.

## Baseline numbers per prd §6.6

| Metric | Baseline | Target | Notes |
|---|---|---|---|
| Completion | 9/10 suite days | 10/10 | osvald_temenos_1 failed on `new_people` |
| Interactions staged | **7/10 world-days** have at least one settled interaction (14 outcome events) | 0 per day | Reviewer audit of the cited outcomes, below |
| State follows the log | 25 findings, not audited one by one | No disagreement | See below |
| Situations live and close | 0 overdue in 10/10; new situations not measurable | None past due | Needs a start-of-day snapshot |
| Canon and scope | 6 findings | No violation | La'mani returned (agnea_throne_1); Gil's charm contradicts `kb/characters/agnea/gil.md` |
| Continuity | Only 1 day ≥ 2 measured, 0 findings | Author confirms | — |

### Reviewer audit of `interactions_staged` (outcome events cited)

- **True (14 events):**
  - hikari_ochette_1: 22, 28, 29
  - hikari_ochette_2: 84, 85 (combat settled; D26)
  - castti_partitio_1: 3, 81, 82
  - castti_partitio_2: 62
  - osvald_temenos_agnea_2: 123
  - world 067042 day 3: 189, 190, 234
  - agnea_throne_2: 28
- **False (6):**
  - osvald_temenos_2: 75 (solitary research)
  - agnea_throne_1: 28 and 66. The judge's own explanation calls these "appropriately settled".
  - agnea_throne_2: 27 (solo practice)
  - osvald_temenos_agnea_1: 4 and 5 (solo rehearsal, walking)
- **Borderline (2):** agnea_throne_1 43 and 67 (ordering a meal, renting a room)

Precision is about 14/22 (64%). Recall is unmeasured; outcome 37 in hikari_ochette_1 was missed.

### Judge quality notes

- **`state_follows_log` mixes real and noisy findings.**
  - **Real:**
    - Throné 235
    - Osvald "traveled to Conning Creek" (56e8c3 event 41) while `where` stays `merry_hills`
    - people who depart (Elena, the minstrel, Maren) but whose `where` doesn't change
    - stale situation `next` text (c0414f `bandit_ambush`)
    - stale people's commitments (Yuki)
  - **Noisy:**
    - complaints that `spot` is null (the schema allows null)
    - a character who leaves a scene but whose `where` doesn't change. By design, where they went is settled at the next part of the day (architecture §5.4).
- **`canon_and_scope` sometimes treats invented minor detail as a canon violation.** For example, a new scholar "Doctor Cyrus Warwick" was flagged, while prd §3 allows new minor characters.

## Findings for the next W steps (D17: one mechanism per recurring failure)

1. **Adjudication settles interactions.** It happens on 7/10 world-days; this is open question 10. It is the most frequent failure, and it recurs across groups.
2. **People's whereabouts and commitments don't follow off-screen events.** Off-screen life writes "X departs for Y" without moving X, and leaves stale commitments and situation `next` texts. This is the open problem "scene outcomes not written back to the state".
3. **Measurement gaps:**
   - There is no start-of-day snapshot (needed for new situations and continuity).
   - Judge precision on `interactions_staged` is about 64%, so the counts are candidate counts and the audit above is the baseline.
