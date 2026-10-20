# Autonomy Spike v3: The World as Storyteller

**Date:** 2026-10-20
**Question:** If the World also acts as storyteller, can it stop the characters from settling into agreement and bring scenes to an end? The storyteller World:
- prepares troubles that touch the main characters
- moves the world when the scene stalls
- ends the scene once it has run its course

**Result:** Inconclusive. The storyteller was slow to act. Its prepared trouble surfaced only in round 16. In round 17 the $0.90 cost cap cut the scene, just as Agnea proposed helping. The characters converged less than in v2, and Throné stayed in character.

## Setup

- **Base:** the v2 harness (see [spike_autonomy_v2.md](spike_autonomy_v2.md)) with three changes:
  - **World prompt:** a "Pace and ending" section. The World's prepared troubles must touch a main character. When the scene stalls or circles, the World moves the world, never the characters. It may add `<end>` once the scene has run its course, after which each character gets one final move.
  - **Round report:** each one tells the World how many rounds have passed since the world last changed.
  - **Narrator:** gets the same word target as the baseline writer, 2,000-3,000 words. It draws on intents for feelings, not for the next line.
- **Unchanged:** the character prompt. No character-side changes were made.
- **Case:** agnea_throne_2, run alone.
- **Run dir:** `runs/spikes/20261020-084935-autonomy3-agnea_throne_2`.

## Results

| | v2 | v3 |
|---|---|---|
| Rounds; how it ended | 32; cost cap mid-scene | 17; cost cap at the trouble's first beat |
| Words per spoken turn, Agnea / Throné | 69 / 48 | 64 / 25 |
| Rounds of mutual reassurance | about 18 | about 5 (rounds 8-12) |
| World spoke (not `—`) | 12 of 32 | 6 of 17 |
| Story | 4,368 words | 1,592 words (the scene was cut short) |
| Cost | $1.22 | $1.15 (World $0.19, Agnea $0.38, Throné $0.33, narrator $0.24) |

## What worked

- **Throné stayed guarded.** Her turns were short ("The stage first, then. I want to see where you performed."). She warms up only to "this isn't bad," and she pockets the offer of a home with "I won't forget it."
- **Less sentiment.** The reassurance runs about 5 rounds instead of about 18, and the story is warm rather than saccharine.
- **The narration has the right shape.** It is told in order, with no echoes, and doesn't pad a short scene.
- **The trouble came from the world.** The missing heirloom recipe book was set up in round 1. In round 16 it pulled Agnea's attention away from the plan to find her father.

## What didn't

- **The storyteller is too patient.**
  - The characters kept walking and talking, so the World judged that the scene was still moving.
  - Its trouble surfaced only in round 16, and the cost cap fell in round 17.
  - The troubles touched the village, not the main characters directly.
- **The narrator voiced a move that never happened.** Throné's preempted line ("Hmm. That's excellent...") appears in the story as spoken. This is a harness flaw: the narrator's record included unspoken moves.
- **Parallel calls lose the prompt cache.** The World, called alone, read its cache almost completely. The two characters, called at the same time, read only about 2,600 cached tokens per call, so they made up 62% of the cost. Calling them one after the other keeps the same simultaneous-choice logic and should roughly halve their cost.

## What it suggests

A storyteller that only reacts to stalls doesn't give a scene its shape fast enough. A planned arc of world events would supply the pacing: a complication by a given point, escalation if nothing gives, and an ending once it resolves. The characters would still choose every move, so this keeps the arc on the world's side.
