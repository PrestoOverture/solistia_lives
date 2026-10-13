# Identity Cards — Blind Voice Test v1 (roadmap 2.1)

**Date:** 2026-10-13
**Result:** 14/16 correct. **Pass** (needs 12).

## Setup

- **Judge:** Codex, model `gpt-6-astra`, reasoning effort high. Job `4d9da7a3`, thread `01a135ea-4e7e-70d2-af7c-81674a3b18a2`, 17.5k tokens.
- **Packet:** the 8 `cards/*.md` plus 16 shuffled, unlabeled lines. There are 2 lines per traveler, each verbatim from the wiki Quotes sections in `kb_raw/pages/`, in no card, and naming no one. The judge wasn't told the 2-per-traveler split.
- **Isolation:** the packet was built outside the repo, because Codex runs with full disk access and the repo holds both the source pages and the key. Codex's session log shows it only listed and read files in the packet directory, then wrote `answers.json`.
- **Contamination:** the judge marked none of the 16 lines as recognized from the game.
- **Key:** `eval/blind/voice_v1_key.json` (gitignored).

## Answers

| ID | Line | Speaker | Judge | |
|---|---|---|---|---|
| L01 | "You are a poison that must be purged." | castti | castti | ✓ |
| L02 | "May I have this dance?" | agnea | agnea | ✓ |
| L03 | "I ask, you answer. Simple." | temenos | osvald | ✗ |
| L04 | "Are negotiations over?" | throne | partitio | ✗ |
| L05 | "Life is too precious to risk." | castti | castti | ✓ |
| L06 | "Greed is a sin, you know..." | temenos | temenos | ✓ |
| L07 | "This was inevitable..." | osvald | osvald | ✓ |
| L08 | "Stand aside, or fight!" | hikari | hikari | ✓ |
| L09 | "I'm starving!" | ochette | ochette | ✓ |
| L10 | "The future hinges on this battle." | hikari | hikari | ✓ |
| L11 | "No need to be stingy." | partitio | partitio | ✓ |
| L12 | "Let's have ourselves a showdown!" | partitio | partitio | ✓ |
| L13 | "What a grand 'ole stage!" | agnea | agnea | ✓ |
| L14 | "What a show." | throne | throne | ✓ |
| L15 | "Ready to be prey?" | ochette | ochette | ✓ |
| L16 | "Ah, a battle of wits." | osvald | osvald | ✓ |

## Misses

- **L03** (Temenos, judged Osvald). The judge read the clipped bluntness as Osvald's short verdicts. Temenos's card covers his polished, ironic register but not the curt tone he takes when pressing someone for answers, although the KB says he coerces answers from suspects.
- **L04** (Throné, judged Partitio). The judge went by the trade vocabulary. In the game Throné says this when Partitio lands a blow, so the line jabs at someone else's turf. This is a weakness in how the line was chosen more than a gap in the cards.
