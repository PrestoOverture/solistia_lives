# KB Stage 2 — Polish

`kb_raw/pages/` holds 609 wiki pages about **Octopath Traveler II**, saved word for word. Turn each one into a clean lore file for a novelist writing stories set in OT2.

**Give each page to a subagent, and have it read the page in full.** Don't use a script to clean pages.

For each page:

1. **Delete** everything a novelist wouldn't use: gameplay (enemies, chests, shops, prices, stats, skills, battle notes, how-to-play), meta content (etymology, music, development, voice actors), anything from other games (OT1, Champions of the Continent), and romanized Japanese. Keep in-world facts, even ones sitting in trivia.
2. **Tidy** what's left into clean Markdown. You may reorder it, merge fragments into sentences, and turn tables into lists.
3. **Never add information.** Every fact in the output must be in the page. A page with little lore gives a short file.
4. **Keep links as they are:** `[text](wiki:Title)`. Stage 3 converts them.
5. **Save** it as `kb/<directory>/<slug>.md`, with the slug from the page's frontmatter and this frontmatter:

```markdown
---
name: <slug>
aliases: [every name it goes by, including the wiki title]
source: [<wiki title>]
---
```

You choose the directories, but `kb/characters/` (the 8 travelers and NPCs) and `kb/locations/` (places) are required.

If a page has no lore left, don't write a file. List it in `preprocess/kb_2_report.md` with a one-line reason.

Only write inside `kb/` and `preprocess/kb_2_report.md`.
