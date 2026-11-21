# Crossroads v1 — one note, three branches (Phase X)

**Date:** 2026-11-21. **Code:** `4fa0fa3` plus the uncommitted Phase X work (settings, `world inject`). **Setting:** `settings/ferry/` (Wren's Ford; mains Ilse, Corwen, Maren). **Models:** Claude (`config/models.yaml`), day 1 only.
**Note:** `A folded note under your door: "Corwen Ash promised the ferry to Tobin Reed after the flood. He has been working on Bram for the boy ever since."` Corwen's promise is a secret on his card only; the KB does not state it.

| Branch | World | Day run | Result | Cost (trace) |
|---|---|---|---|---|
| control (no note) | `20261121-080000-c0c0c0` | `20261121-082642-419df6` | stopped at day 1 night by `max_cost_usd` ($20) | $20.18 |
| a1: note → Ilse | `20261121-080000-a1a1a1` | `20261121-082642-506f4b` | day 1 complete | $9.81 |
| b2: note → Maren | `20261121-080000-b2b2b2` | `20261121-082642-d77867` | failed at turn 4 | $0.85 |
| b2 rerun | same | `20261121-102149-304fc8` | failed at turn 12 (retry dropped `odds`) | $2.16 |
| b2 rerun, World retries 2 | same | `20261121-103931-f63d12` | morning only, then the $10 cap | $10.03 |

Starting state $0.44. First round $31.28 trace against a $25 budget; the b2 reruns $12.19 against $12. Phase X total $43.47 trace. The comparison below covers morning to evening, which both control and a1 finished.

## Where the note went (a1)

Only Ilse's intents can be attributed to the note. Maren, who got nothing, already planned differently in the two branches from her first plan (a1: sound out Corwen; control: sound out Ilse). One sample per branch cannot separate scene-level differences from sampling noise.

1. **First plan (#5).** Ilse's intent says "Corwen has been pushing Bram toward Tobin". Only the note says this; Hester's shared line says only that Corwen visited the ferry house. She goes straight to Bram alone. In control she first asks Hester for more, and goes to Bram only in the afternoon, after Hester tells her "He's not going to ask."
2. **With Bram (#51, #57).** She accuses: "You going to end that because Corwen feels guilty about Aled?" When Bram says "you're not wrong to ask", her intent reads it as "He all but told me he'd decided on Tobin". The note shapes how she reads him.
3. **Target shifts to Corwen (#71, #118).** Afternoon: "If I can't move Bram directly, moving Corwen is the next best thing." Evening: she tells Corwen at Bram's table, in front of the room, that a Calloway purchase makes Tobin's ferry "Not a life. A sale."
4. **Spread (#150, #170).** Tobin answers in public: "You think I'd sell what my father died trying to have." Maren's night plan now counts it: "Tobin claims he won't sell." The note reached the bridge buyer's picture of the world through two people who never saw it.

In control, Ilse states her claim publicly in the afternoon ("I want the boat, Uncle … Name it to me"). In the evening, Corwen says aloud that he wants Tobin named, and Bram asks Corwen what to do. The evening is about Corwen's influence, not about Calloway.

**The secret never surfaced in either branch.** In a1 Ilse never says "promise" to anyone, and never tests whether the note is true. She uses it as a reason to suspect Corwen, not as information to deploy.

## b2: the note to Maren (morning only)

Maren's first plan (#6) cites it: "The note suggests he's been working behind the scenes", and she goes to Corwen "without revealing the anonymous note". Maren in a1, with no note, also went to Corwen first, so the visit itself is not the note's doing. In the talk she reads Corwen's "the lad" as Tobin and his motive as personal, "maybe out of guilt over Aled's death" (#27). She never names the promise. Ilse, without the note, tells Bram "Then name me" in the morning, close to control's afternoon claim.

Both recipients did the same thing: they kept the note to themselves and used it to read other people. Neither one passed it on or tested it.

## Failures and costs

- **b2.** In round 2 a minor (Dag) won the floor and the World replied `resolution: null`. The first error message asked only for `about`. The retry added `about` but left `resolution` null, and the run died. In control and a1, minors won 27 times and the World gave a resolution each time. So this is a one-off slip that a single retry did not fix. It is not systematic, and today's minor-winner change (`4fa0fa3`) did not obviously cause it.
- **Control cost 2× a1, on a shorter day.** The World's prompt cache did not hold in control: 2.76M uncached input tokens against 63k in a1, with uncached input growing every call (24k → 69k). The World's calls cost $10.35 against $2.63. One Ilse call ran 12 turns and cost $1.09. The cause is not verified. a1 is the representative cost: **about $10 trace per 3-main day**.
- **World retries.** The first b2 rerun died when the World's corrected reply fixed the reported op but dropped `odds` and `failure`. With `retries: 2` for the World (`config/models.yaml`), two replies that failed twice were accepted on the third try.
- **The cache failures come from the relay's routing.** Each SDK session stores its replies in `runs/<run>/.sdk/projects/*/*.jsonl`. Across the 23 Claude sessions of these runs, message ids come in two formats. All 9 sessions answered with Anthropic-style ids (`msg_01…`) averaged 450–810 uncached input tokens per request. All 13 answered with hex ids (`msg_2dcb0…`) averaged 7.9k–41.6k, with uncached input growing every turn. One session that switched mid-way averaged 9.3k. A session keeps its backend, and the code, prompts and model are the same on both, so the relay is sending part of its traffic to an upstream that ignores `cache_control`. Control had all five sessions on the hex backend; a1 had its World on the official one. Which backend a session gets decides whether a day costs $10 or $30 in trace.
- **Character calls** carry 1.5–2.1M uncached input tokens a day in both branches. This is the largest remaining cost.
- **Odds on talk.** Of a1's 47 resolutions, 13 failed, mostly on plain speech ("What changed?" → "too broad—Bram doesn't know what she's asking"). Failed rolls on ordinary dialogue make conversations lurch.

## Day 2 (2026-11-21, World and character `retries: 2`)

| Branch | Runs | Reached | Cost (trace) |
|---|---|---|---|
| control | `20261121-112336-9e73cc`, `20261121-112946-17f1ad` | day 3 morning | $21.72 |
| a1 | `20261121-112336-101985` | day 3 morning | $22.93 |
| b2 | `20261121-112336-71b8b9` (character retry failed), `20261121-115816-a3ce83` (relay quota ran out, 403), then `20261121-172010-ae6d7e`, `20261121-172446-964077` (2026-11-21, after a recharge) | day 3 morning | $19.76 |

**Ilse is named in both control and a1. The note changed how she got there and what became public.**

- **Control.** Ilse crosses the river at night with Bram on day 1 night, the fear she had not faced in fifteen years (situation `ilse_crossed`, opened by the World). At the naming Bram names her. The promise is never spoken in public. That night Corwen admits it to Tobin alone: "I told you the ferry would be yours and it won't be." Maren puts her offer to Ilse; Ilse walks off without answering.
- **a1.** The secret surfaces, through two memory errors:
  1. Ilse's day 1 summary (`memory/ilse.md`, which keeps only the latest day) leaves the note out. The author note is perceived once, on day 1, so by day 2 she has lost its text.
  2. The World remembers the note. It opened `ilses_card` and wrote "The note in Ilse's pocket names a promise Corwen made" (#230, #234). Ilse, prompted by that, fills in content and source: "Maren wrote that yesterday. Corwen's promised Tobin the Calloway money" (#239).
  3. The World plays Bram reading the real note: "I'll want to speak with Corwen this afternoon" (#242).
  4. In the afternoon Ilse tells Maren "You wrote me that note". Maren accepts an act she never did: "She's referring to a note I wrote her" (#263). Maren then gives her the bridge, the price and the timeline in front of the room.
  5. At the landing Bram asks in front of the village: "Corwen. Did you promise that boy the ferry?" "Yes." He names Ilse (#311–#319). That night Ilse, now knowing the bridge comes either way, tells Maren "I'll need time".
- **b2. Nobody is named.** At evening's end the World drops `corwens_promise` and `tobins_exposed_position` and marks the naming commitments of Corwen, Maren, Bram and Tobin `broken` (#306–#307). At night Tobin, Corwen and Ilse wait at the cable posts (scene 13). Bram walks down in a separate scene (14), arriving after scene 13 has closed, so no scene holds him at the landing. The World's next line is "Whatever was said there is said" (#327) and the clock moves to day 3. Ilse's summary ends "Whatever Bram said, he said it." The climax happened in the gap between scenes, and the state records no successor. The promise never surfaces; Corwen admits only that he knew about the bridge for a week and that he does not believe Ilse can go back on the water (afternoon, boatyard).
- **b2: a false summary.** In the morning Maren is held at the inn (#223, a failed roll on leaving) and never reaches the ferry house; the World releases her meeting as `broken` and Ilse's plan says "Maren never came". Maren's day 2 summary says "I kept my commitment at the ferry house and laid the full Calloway offer on the table." The World's own offscreen line (#226) also contradicts scene 8: it has Bram find Ilse at the inn when the scene had them at the ferry house.
- **b2 (day 1).** Maren cites the note in her plans ("Corwen confirmed what the anonymous note said") and uses it to frame Corwen as the one who put Tobin in an impossible position (#159). She never names the promise.

**Framework findings.**
- **Author notes don't persist.** An author note lives only in the recipient's first perception and whatever her summary keeps. A note the character doesn't act on that day is gone the next, while the World, which keeps the full log, still knows it.
- **Mains accept claims about their own past.** Maren took "you wrote me that note" as true. A main has no record of her own acts beyond her summary.
- **A decisive event can fall between scenes.** The World can resolve or drop a situation without playing it (b2's naming). Nothing makes the payoff of a due situation happen on screen.
- **Summaries can invent the day.** Maren's summary records a meeting that did not happen; with the summary as a main's only memory, the invention becomes her past.
- **The World writes mains' reactions.** Outcomes such as "she opens with the offer before she's read the room, closing Ilse off" (b2 #140) and "she hedges" (#144) narrate Maren's next move. Maren reads them as warnings, calls them "the world note", and does the opposite. This is a semantic breach of "no scene call moves a main", which code can't check.

## Verdict

A private note to one main changed what she did within the first plan, and its effect reached a third main by night, through people who never read it. It did not bring the secret into the open on day 1. The effect is visible only by comparing branches. A reader of a1 alone could not tell the note mattered. Given to either rival, the note was kept, not used. By day 2 the note decided what the village learned. Ilse is named either way, but only in a1 is Corwen's promise said aloud at the landing. It got there by a chain of errors (a forgotten note, a confabulated author, a main accepting a false past) that happens to read as a strong story. In b2, given to the buyer, the note went nowhere public, and the naming itself was lost between two scenes, so b2 has no ending to compare.
