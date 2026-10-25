# World metrics v2 — W2 (involves → staged by code, D31)

**Date:** 2026-10-25. **Code:** commit `900f905`. **Tool:** `story-engine eval world` (same judge and prompt as [world_v1.md](world_v1.md)).
**Inputs:** fresh simulation suite, day 1 only: `run-suite --mode simulation --stop-after day` → `runs/suites/01d4fbff9d473660abaaddd32b5bfb99.json`.
**Cost:** suite $28.84, judge $1.92 (including the two failed judge runs). Total about $30.76.

## Results

| Case | World | Day run | Judge run | Outcomes | Forced staged | Reviewer: settled interactions |
|---|---|---|---|---|---|---|
| osvald_temenos_1 | `20261025-092232-0cc6f6` | `20261025-092233-5261cc` | `20261025-100947-76a4a4` (judge failed) | 2 | 0 | 0 (103, 104: resting) |
| osvald_temenos_2 | `20261025-092253-40d404` | `20261025-092254-a96aa8` | `20261025-101100-c37979` | 1 | 0 | **33** (Temenos grants Osvald archive access) |
| agnea_throne_1 | `20261025-092217-76d799` | `20261025-092218-d43ed4` | `20261025-101211-96fd49` | 4 | 0 | **33** (Throné confronts the pickpocket); borderline 32 (performs to a crowd) |
| agnea_throne_2 | `20261025-092200-b68888` | `20261025-092201-817ae3` | `20261025-101308-273a81` | 2 | 0 | **91** (embraces from Garud and Pala) |
| hikari_ochette_1 | `20261025-092220-619148` | `20261025-092222-436e28` | `20261025-101356-9ec0bc` (judge failed) | 0 | 0 | 0 |
| hikari_ochette_2 | `20261025-094015-a632ff` | `20261025-094017-8a60e8` | `20261025-101458-322695` | 0 | 0 | 0 |
| castti_partitio_1 | `20261025-094023-e6300f` | `20261025-094025-ace415` | `20261025-101604-546cf9` | 0 | 0 | 0 |
| castti_partitio_2 | `20261025-094323-682916` | `20261025-094324-3b4935` (**day failed**) | `20261025-101655-78d5a8` | — | — | — |
| osvald_temenos_agnea_1 | `20261025-094415-4b3a81` | `20261025-094416-e6356a` | `20261025-101655-b81143` | 8 | 0 | 0 (travel, observing, resting) |
| osvald_temenos_agnea_2 | `20261025-094435-524687` | `20261025-094436-ff89ad` | `20261025-101744-431ee3` | 6 | 0 | **4** (the baker greets her and gives her a sandwich); borderline 77 (renting a room) |

The reviewer read all 23 part-of-day outcomes, not only the judge's citations.

## Against W2's Test

| Metric | W1 | W2 | W2 pass condition | Pass |
|---|---|---|---|---|
| Completion | 9/10 | 9/10 | ≥ 9/10 | yes |
| Interactions staged (world-days with ≥1 settled interaction, reviewer) | 7/10 (14 events) | **4/9 completed** (4 events, plus 2 borderline) | ≤ 1/10 | **no** |
| Outcomes per day | 1-8 | 0-8 (23 total) | — | — |

**W2 fails its Test.**

## Diagnosis

- **`verdict_forced_staged` fired 0 times in 9 days.** For all 23 settled verdicts, the World wrote `involves: []`, including outcome 33 (40d404), which names Temenos, a main character, and 91 (b68888), which names Garud and Pala. The code path works (unit tests); the World doesn't report who is involved when it has already decided to settle. Moving the question into a field didn't move the judgment out of the World's session: the same call that wants to settle also fills `involves`.
- The count of settled interactions fell (14 → 4 events, 7 → 4 world-days). Part of that may come from the rewritten adjudicate wording, and part is run-to-run variance; one suite can't separate them.
- Two of the four remaining cases are the World introducing people into an outcome (the baker, Garud and Pala), not the character's plan aiming at them.

## Other findings

- **Day failure (castti_partitio_2):** "Character action validation failed after one retry: reply must be a JSON object". A character reply problem, not adjudication. W1's one failure was different (`new_people` named Temenos).
- **Judge failures, 2/10:** the judge cited scene events under `interactions_staged` twice in a row (76a4a4: [47, 50, …, 71]; 9ec0bc: [24]). The citation rule holds, but the run then fails instead of dropping the finding.
- **World retries:** 29 `world_validation_failed` across the suite, all recovered by retry; the most common is "World event of must name a main character whose attempt this call resolves" (9, all in `e6356a`), then minor_moves for a person not at the place (6).
- `state_follows_log` and `canon_and_scope` counts are similar to W1 (3 and 0-2 per day) and weren't audited.
