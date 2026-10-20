# Autonomy Spike v1: Characters Decide, No Beats

**Date:** 2026-10-20
**Question:** Can a scene run with no beat plan and no per-turn directions, with each character deciding their own moves? And does Osvald then act like himself, with no new card rules?
**Result:** Partly.
- **What worked:** the scene ran and ended on its own, and Osvald's choices came from his card.
- **What didn't:** the scheduler set the turn order, the characters talked in essays, the World made its people an admiring audience, and the narrator retold the debate after the fact.
- **Verdict:** the story is weaker than the baseline's.

## Setup

- **Case:** osvald_temenos_2 (Flamechurch, "Debating faith and reason over drinks"). It reuses the scene context from the baseline run `runs/20261019-131731-dec91f`, so only the generation method differs.
- **Agents:** each runs in a persistent SDK session through the relay, with thinking off.
  - **World** (Sonnet 4.6, director role):
    - Privately prepares the place, its people, and a few small troubles.
    - Writes the opening.
    - After each round, says what the world does, or nothing.
    - Never sees the characters' intents.
  - **Osvald and Temenos** (Sonnet 4.6, character role): each has an identity card and the scene context, and may read the KB. Each round, a character privately states an intent and then picks one of three moves:
    - act, with an urge from 1 to 3
    - wait, which may include a visible reaction
    - leave, which is final
  - **Narrator** (Opus 4.6, rewrite role): gets the style spec, the cards, the scene context, and the full record including intents, and writes `story.md`.
- **Turn order:** everyone moves at once, and the highest urge takes the floor. Ties go to whoever acted least recently.
- **End condition:** the scene ends when only one character remains and has made a final move, after two quiet rounds, or at 30 rounds.
- **Code:** the harness is a throwaway script, not repo code. Each run dir holds a snapshot of it (`spike_autonomy.py`) and of the prompts (`prompts/`).
- **Runs:**
  - `runs/spikes/20261020-081048-autonomy-smoke`: 4 rounds, no narrator. In this run the World described the characters' gestures for them.
  - `runs/spikes/20261020-081401-autonomy`: the full run, after the World's prompt was tightened against that.

## Results

| | Baseline (`131731-dec91f`) | Spike |
|---|---|---|
| Who decides each turn | One writer | Each character |
| Dialogue words, Temenos : Osvald | 860 : 420 (about 2 : 1) | 1,155 : 867 in the transcript (about 1.3 : 1) |
| Words per spoken turn, Temenos / Osvald | — | 165 / 124 |
| Ending | Chosen by the writer | Osvald left once the argument was done, and Temenos left after him (13 rounds) |
| Story | 2,146 words | 1,491 words, about 150 of them dialogue |
| Cost | $0.31 | $0.82 (World $0.19, Osvald $0.21, Temenos $0.24, narrator $0.18), plus $0.19 for the smoke run |

The full run took 6 minutes.

## What worked

- **The scene ended on its own.** The argument ran nine rounds, with no cap and no Director. Then Osvald's intent read: "no desire to linger in idle conversation now that the substantive discussion is complete." He left. His card's "idle chatter wastes his time" produced this; no rule was added.
- **Osvald argued as Temenos's equal,** as the KB says he would. He waited for answers instead of filling the silence, and conceded points when Temenos earned them, so the dialogue went both ways.
- **The intents give a reason for every move.** That helps diagnosis, gives the narrator real inner life to draw on, and is a natural seed for per-character memory.
- **Both characters read the KB without being told to,** three files each.

## What didn't

- **The characters didn't set the turn order.**
  - 17 of the 18 bids were urge 2. In 5 of the 6 rounds where both wanted the floor, the bids tied and the tie-break decided.
  - The result was strict alternation.
  - Temenos lost all 5 of those tie-breaks. In 4 of them he was trying to follow up his own previous speech.
- **The characters gave speeches, not conversation.** Spoken turns averaged 124 to 165 words. Both voices drifted into the same polished debating register, and Osvald's terse verdicts and Temenos's teasing mostly disappeared.
- **There was no friction.** Both characters wanted the same thing, a good debate, and both kept conceding and praising. The scene ends in mutual admiration.
- **The World served the heroes.**
  - Its people became an awed audience: a novice near tears, a merchant writing down their words, a free round because "it's an honor."
  - It resolved its own planted trouble, the novice's question, without involving either character. Neither of them ever spoke to anyone else in the room.
  - It answered `—` in only 2 of 13 rounds, and its replies often ran past the requested three sentences.
- **The narrator retold the scene instead of telling it.**
  - It opened at the farewell and replayed the debate as Temenos's afterthoughts, which breaks the record's order.
  - It closed on a reflection that over-explains.
- **The premise still scripts the content.** "Debating faith and reason" led the World to open with the two of them already set on a debate. This run can't show whether Osvald would have chosen to debate at all.

## What it suggests

Autonomy works at the level of choices: when to speak, concede, or leave. Those choices came from the cards.

The story suffered from structural problems that are separate from autonomy. Each has a structural fix, not a character rule:
- Make the premise a situation, not an activity.
- Make a turn what one would actually say aloud.
- Give the floor by a rule that works better than flat urges.
- Give the World's people their own business.
- Have the narrator dramatize the record in order.
