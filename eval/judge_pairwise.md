# Story Judge: Pairwise

You are comparing two short stories, `story_A.md` and `story_B.md` in this folder. Both were written from the same characters, place, and scenario. They are fan fiction set in Solistia, the world of Octopath Traveler II, after the game's true ending. Judge only the texts in front of you.

## What the stories are meant to be
- **Setting:** after the true ending. Vide is defeated, the Moonshade Order is broken, and the eight travelers (Osvald, Temenos, Agnea, Throné, Hikari, Ochette, Castti, Partitio) have finished their journeys. All eight are friends.
- **Scope:** a self-contained episode of 2,000 to 3,000 words. It can be a reunion, a conversation, or a small incident that begins and ends within the story. No world-level threats, no returning enemies from the game, and nothing left open for a sequel.
- **Style:** close third person from one character's point of view, more narration than dialogue, and voices that can be told apart without speaker tags.

## How to compare
Compare the stories on each axis, then overall.
- **Lore accuracy:** which one gets Octopath Traveler II right? New minor characters, new places, and the episode's own incident are allowed. Contradicting the game is an error, and so is reviving a defeated enemy or starting a world-level threat.
- **Character voice:** in which one could you better tell who is speaking with the names removed, and do the characters act more like themselves?
- **Readability:** which has better prose, pacing, and sense of place?
- **Overall:** which would you rather give a reader who loves these characters?

Use "tie" only when you genuinely can't choose. Ignore which file comes first, and don't prefer a story for being longer.

## Output
Write `verdict.json` in this folder, and nothing else:

```json
{
  "lore": "A",
  "voice": "B",
  "readability": "B",
  "overall": "B",
  "reasons": "..."
}
```

Each axis and `overall` is `"A"`, `"B"`, or `"tie"`. `reasons` is two to four sentences on what decided it, pointing to specific passages.
