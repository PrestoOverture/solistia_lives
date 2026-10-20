# Autonomy Spike v2: Structural Fixes

**Date:** 2026-10-20
**Question:** Do the five structural fixes from [v1](spike_autonomy_v1.md) make autonomous scenes read better? The fixes:
- a situation as the premise
- conversational turns
- the floor going to whoever was addressed
- a World whose people go about their own business
- a narrator that tells the scene in order

**Result:**
- **The fixes worked.** Turns got short, the floor rule produced natural back-and-forth, the World went quiet, and the narration runs in order.
- **A deeper problem surfaced.** Left alone, the two characters settle into agreeing with each other, and neither scene ended on its own. Both hit the cost cap.
- **Verdict:** both stories lose to their baselines in blind pairwise judging (see below).

## Blind judging

Setup:
- **Judging:** each pair was packed twice: once in random order, once swapped. Each packet was judged in its own Codex session (`gpt-6.1-sol`, effort high) using `eval/judge_pairwise.md`, with the packet as the working directory, outside the repo.
- **Audit:** the session logs show no reads outside the packets, and the packet stories are byte-identical to the runs.
- **Raw verdicts:** `spike_autonomy_v2_verdicts.json`.

| Pair | Lore | Voice | Readability | Overall |
|---|---|---|---|---|
| osvald_temenos_2 | spike, spike | baseline, baseline | baseline, baseline | **baseline, baseline** |
| agnea_throne_2 | baseline, tie | baseline, baseline | baseline, baseline | **baseline, baseline** |

The judges' reasons match the diagnosis below:
- **Osvald and Temenos:** they sound like "mutually approving lecturers".
- **Agnea and Throné:** the two women give "similarly expansive reassurance", and the story "stalls through repeated consolations".
- **Repetition:** the judges flagged the narrator repeating passages.
- **Lore:** the spike won lore in the Osvald pair. The baseline's line about a price paid "in blood or suffering" gives Osvald Harvey's outlook.

## Setup

- **Same harness as v1, plus the five fixes:**
  - Each move now names its addressee. The addressee answers first; anyone else needs urge 3 to cut in.
  - The World answers in at most two sentences, or `—`.
  - The narrator tells the scene from start to end, with no frame or flashback.
- **Snapshots:** each run dir holds a copy of the prompts and the script.
- **Cases:** each case reuses its baseline run's scene context.

| Case | Premise | Baseline |
|---|---|---|
| osvald_temenos_2 (Flamechurch) | "Osvald and Temenos meet for a drink" (the suite says "Debating faith and reason over drinks") | `20261019-131731-dec91f` |
| agnea_throne_2 (Cropdale) | "Agnea drags Throné to a festival" (unchanged) | `20261019-131731-957910` (the suite's best) |

- **Limits:** a cap of 40 rounds, and $0.90 per scene before the narrator.
- **Runs:** both ran in parallel through the relay.
  - `runs/spikes/20261020-083135-autonomy2-osvald_temenos_2`
  - `runs/spikes/20261020-083136-autonomy2-agnea_throne_2`

## Results

| | Osvald + Temenos | Agnea + Throné |
|---|---|---|
| Rounds; how it ended | 18; cost cap, as the two walked out to the cathedral | 32; cost cap, mid-scene, as Pala arrived |
| Words per spoken turn (v1: 124–165) | Osvald 76, Temenos 73 | Agnea 69, Throné 48 |
| Floor went to the addressee | 15 of 18 rounds | 28 of 32 rounds |
| Bids at urge 2; interruptions | 22 of 23; none | 39 of 45; none |
| World spoke (not `—`) | 4 of 18 rounds | 12 of 32 rounds |
| Story | 2,159 words | 4,368 words (the target is at most about 3,000) |
| Cost | $1.12 | $1.22 |

Both cost more than planned. With the two runs in parallel, the relay's prompt cache mostly missed: Osvald's calls read only about 2,600 cached tokens each time and rewrote the rest, roughly doubling the cost per call. Spikes on the relay should run one at a time. Total: $2.34.

## What worked

- **Conversation, not essays.** Osvald got his verbal tics back ("Hmm...", "Nonsense."). He waited out a silence, and Temenos misread it and rephrased his question.
- **The debate came from the characters.** With only "meet for a drink" as the premise, Osvald steered the talk toward his research by asking Temenos how the Sacred Flame feels to wield. Temenos brought up Crick without being asked.
- **The World stayed in the background.** Its people went about their business: an old pilgrim arguing about the eternal night, chickens, a pie seller. Cropdale greets Agnea as its returning star, which fits her hometown.
- **Small in-character choices emerged.** Throné studies the pie's lattice like a craftswoman, and keeps a hand near her dagger out of habit.

## What didn't

- **The characters converge.** Nothing pushes against the mutual agreement, so it runs on:
  - **Agnea and Throné:** for about 18 rounds on the festival stage, they hold hands, embrace, and trade reassurances ("you won't disappear"). Guarded Throné opens up within minutes, which contradicts her card.
  - **Osvald and Temenos:** they agree their way to a shared theory and praise each other ("a better answer to the problem of evil than fifteen centuries of church doctrine").
  - The World was told not to rescue a stalled conversation, so it didn't.
  - Neither of the World's prepared troubles came up: a fussy contest judge, and a cart's wobbly wheel. Neither involved the main characters.
- **No scene ended on its own.** In v1 the argument concluded and Osvald left. This time both scenes ran on until the cost cap.
- **The narrator transcribes.**
  - In Osvald + Temenos, it keeps nearly every line verbatim. In at least four places it states a thought and then repeats it as dialogue ("Not evaluation—incompatibility.").
  - In Agnea + Throné, it ran 46% over length and added a closing line that Throné never said.
- **The World changed the premise.** Its private notes made the festival a weekly market: "not the grand annual festival."

## What it suggests

Autonomy works at the level of each move, and those moves are in character. What's missing is shape across the whole scene: conflict, pressure, and an ending. Left alone, the model's agreeable default outlasts a card's traits.

The beat plan supplied exactly that shape. A hybrid could keep both:
- **Characters** keep their autonomy. No director gives them per-turn directions.
- **The World becomes a storyteller.** It sets up situations with real stakes for the main characters, raises pressure when a scene stalls or loops, and ends a scene once it has run its course. This is the role of RimWorld's storyteller, or a drama manager in interactive drama.
