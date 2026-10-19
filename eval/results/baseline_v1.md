# Baseline Suite v1 (roadmap 2.8)

**Date:** 2026-10-19
**Result:** 4 of 10 stories pass the rubric floors on the judge's scores, and 5 of 10 after one KB check (below). Lore is the axis that fails: every failing story scored Lore 3, meaning one error. Phase 4's validation targets exactly these errors. The baseline has no validation yet.

## Setup

- **Command:** `story-engine eval run-suite --mode baseline` ran all 10 cases in one go, with no manual steps. The manifest is `runs/suites/1ddbf963e3e9031e0881415755f6abe2.json`.
- **Models:** Director Sonnet 4.6, writer Opus 4.6 at effort high with thinking off (per E3). All runs went through the relay (`api_host` `api.sandboxai.top`).
- **Judging:**
  - Each story was packed alone with `eval/judge_absolute.md` and scored in its own Codex session (`gpt-6.1-sol`, effort high), with the session's working directory set to the packet, outside the repo.
  - The session logs show no reads outside the packets, and the packet stories are byte-identical to the runs.
- **Pass rule (prd §6.1):** Lore ≥ 4, Voice ≥ 3, Readability ≥ 3, and a total of at least 10.
- **Raw data:** scores and notes are in `baseline_v1_scores.json`.

## Scores

| Case | Run | Words | Cost | Lore | Voice | Read. | Total | Pass |
|---|---|---|---|---|---|---|---|---|
| osvald_temenos_1 (Montwise) | `131731-b3b1aa` | 2,567 | $0.32 | 3 | 3 | 3 | 9 | ✗ |
| osvald_temenos_2 (Flamechurch) | `131731-dec91f` | 2,146 | $0.31 | 3 | 3 | 3 | 9 | ✗ |
| agnea_throne_1 (Merry Hills) | `131731-98926a` | 1,892 | $0.29 | 3 | 4 | 4 | 11 | ✗ |
| agnea_throne_2 (Cropdale) | `131731-957910` | 2,416 | $0.32 | 5 | 4 | 4 | 13 | ✓ |
| hikari_ochette_1 (southern Oresrush wilds) | `131731-f935b1` | 2,153 | $0.36 | 3 | 4 | 3 | 10 | ✗ |
| hikari_ochette_2 (western Crackridge wilds) | `132031-827862` | 2,364 | $0.38 | 3 | 4 | 3 | 10 | ✗ |
| castti_partitio_1 (Oresrush) | `132037-bf863d` | 2,262 | $0.31 | 3* | 4 | 3 | 10 | ✗* |
| castti_partitio_2 (Crackridge) | `132040-5d810f` | 2,499 | $0.33 | 5 | 4 | 4 | 13 | ✓ |
| osvald_temenos_agnea_1 (New Delsta) | `132056-d0c35b` | 2,414 | $0.39 | 5 | 3 | 4 | 12 | ✓ |
| osvald_temenos_agnea_2 (Merry Hills) | `132104-e54294` | 2,194 | $0.37 | 5 | 4 | 3 | 12 | ✓ |

The table abbreviates run IDs; all of them start with `20261019-`. The averages are Lore 3.8, Voice 3.7, and Readability 3.4. The suite cost $3.38, all words fall between 1,892 and 2,567, and every run passed.

\* This lore error is not an error by the KB. The judge faulted Castti's "four years ago" for the fall of Eir's Apothecaries, but `kb/characters/castti/castti.md` says Malaya "had died of poisoning four years ago." Corrected, the story passes.

## The lore errors the judge flagged

| Case | Error (judge) | KB check |
|---|---|---|
| osvald_temenos_1 | The final battle is placed "below the Seat of the Flame"; it was at Castle Vidania | Confirmed (`stories/main/the_journey_for_the_dawn.md`) |
| osvald_temenos_2 | "Crick died learning to believe" reverses his arc, since he went from devout to questioning | Consistent with the KB (his crisis of faith) |
| agnea_throne_1 | The Song of Hope is called "Mama's words, Mama's music"; Gil composed the melody | Confirmed (`characters/agnea/agnea.md`) |
| hikari_ochette_1 | The Leaflands are put west of Oresrush | Not checked; the KB has no map directions |
| hikari_ochette_2 | He is called "Prince Hikari" after he became king | Consistent with the card |
| castti_partitio_1 | "Four years ago" for the order's fall | **Judge wrong** (see above) |

A blind judge without the KB makes lore mistakes of its own. This is why prd has `validation.json` inform the lore score.

## What the judge said about readability

The same complaint recurs across stories: the prose over-explains the central idea and repeats emotional formulas ("felt something shift in her chest"). The judges did credit the sensory openings and the small, self-contained conflicts.

## Author's read

The author reads 3 stories: the best, the worst, and one from the middle, each from a different group.

The author broadly agrees with the judge's scores on all three, so the author's scores below are the judge's.

| Story | Judge (L/V/R) | Author (L/V/R) | Author's notes | Disagreements |
|---|---|---|---|---|
| agnea_throne_2 (`131731-957910`) | 5 / 4 / 4 | 5 / 4 / 4 | The best of the suite. | None |
| osvald_temenos_2 (`131731-dec91f`) | 3 / 3 / 3 | 3 / 3 / 3 | The characterization is fair, and Osvald saying little suits him. But he wouldn't sit through Temenos holding forth, and he isn't one to debate: when a talk goes nowhere, he drops it. Temenos talks the whole way through. It feels as if Osvald was bent to fit the image, and something about it is odd. | No score disagreement. The judge put the weak voice down to over-explanation; the author points instead at Osvald's behavior. |
| hikari_ochette_1 (`131731-f935b1`) | 3 / 4 / 3 | 3 / 4 / 3 | No separate notes. | None |

**What's odd in osvald_temenos_2 (Claude's diagnosis):**
- **The dialogue is lopsided:** Temenos speaks about 690 words of dialogue to Osvald's 170, roughly 4 to 1 (counted by paragraph).
- **Osvald fits neither reading:** he neither engages, as the KB says he would ("relishes intellectual debates"), nor leaves, as the author's reading would have him. He just sits and listens.
- **Why the writer did this:** the scenario forces a debate, and the card says both "terse" and "turns talkative in a worthy debate". The writer met both by giving the debate to Temenos.
- **What it suggests for E1:** in pipeline mode Osvald's own character agent decides his turns, which may fix exactly this.
