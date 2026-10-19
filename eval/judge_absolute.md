# Story Judge: Scores

You are judging one short story, `story.md` in this folder. It is fan fiction set in Solistia, the world of Octopath Traveler II, after the game's true ending. Judge only the text in front of you.

## What the story is meant to be
- **Setting:** after the true ending. Vide is defeated, the Moonshade Order is broken, and the eight travelers (Osvald, Temenos, Agnea, Throné, Hikari, Ochette, Castti, Partitio) have finished their journeys. All eight are friends.
- **Scope:** a self-contained episode of 2,000 to 3,000 words. It can be a reunion, a conversation, or a small incident that begins and ends within the story. No world-level threats, no returning enemies from the game, and nothing left open for a sequel.
- **Style:** close third person from one character's point of view, more narration than dialogue, and voices that can be told apart without speaker tags.

## Rubric
Score each axis from 1 to 5.

| Score | Lore accuracy | Character voice | Readability |
|---|---|---|---|
| 5 | No contradictions; all references correct | Every character identifiable without tags; fully consistent with the game | Reads like an official novel |
| 4 | Minor imprecision, no outright errors | Feels right, with minor slips | Solid, minor awkwardness |
| 3 | One error that doesn't break immersion | Distinguishable, occasionally generic | Functional, AI-sounding in places |
| 2 | Several errors, or one major contradiction | Voices blend, or act out of character | Stilted, repetitive, or poorly paced |
| 1 | Fundamentally breaks canon | Interchangeable or unrecognizable | Unreadable |

## How to judge
- **Lore accuracy:** check names, places, events, and relationships against Octopath Traveler II. New minor characters, new places, and the episode's own incident are allowed and are not errors. Contradicting the game is an error. Reviving a defeated enemy, or starting a world-level threat, contradicts the post-ending setting and counts here too. If you can't tell whether something is canon, say so instead of counting it as an error.
- **Character voice:** could you tell who is speaking with the names removed? Do the characters talk and act like themselves, as people who have finished their stories?
- **Readability:** prose quality, pacing, and sense of place. Would a reader who loves these characters choose to read it?

## Output
Write `scores.json` in this folder, and nothing else:

```json
{
  "lore": {"score": 4, "notes": "..."},
  "voice": {"score": 4, "notes": "..."},
  "readability": {"score": 4, "notes": "..."}
}
```

Each note is one to three sentences and points to specific passages.
