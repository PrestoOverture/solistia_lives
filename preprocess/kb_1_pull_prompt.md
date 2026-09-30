# KB Stage 1 — Classify and Pull

This is stage 1 of 3 in building `kb/`, a lore base for fiction set in **Octopath Traveler II (OT2)**. The stages are: 1 pull, 2 polish, 3 link. **This stage has exactly two jobs:**

1. Decide, page by page, whether a wiki page belongs to OT2.
2. For every page that does, save **all of its text, unedited**.

Don't clean, summarize, shorten, rewrite, or add anything. Stage 2 does the cleaning, and it needs the complete original to work from.

**Source:** the Octopath Traveler Fandom wiki, `https://octopathtraveler.fandom.com/api.php`. The wiki covers the whole series (~4,700 pages).

**Before you start:** move the current `kb/` contents to `kb_raw/kb_v2/`, and move `preprocess/kb_build_report.md` there too. Don't delete them, and don't reuse anything from them or from `kb_raw/kb_v1/`.

## Step 1 — Candidates

List every page that might hold OT2 lore: characters, NPCs, places, factions, gods, lore, the main story, side stories, and in-game books or journals. **When unsure, include the page;** step 2 filters. Skip only namespaces and categories that clearly hold no lore: files, templates, users, items, equipment, skills, jobs, and enemy stat pages.

## Step 2 — Verdict (subagents)

A subagent reads each candidate page in full and gives it one label:

- `ot2`: the page is about OT2.
- `mixed`: the page covers OT2 and another game (OT1, Champions of the Continent). Keep the whole page, because stage 2 removes the other game's parts.
- `not_ot2`: nothing on the page is OT2 lore.

It also writes a one-line reason. The verdict is the only judgment in this stage.

## Step 3 — Pull the text (script)

For every `ot2` or `mixed` page, fetch the **rendered** page (`action=parse&prop=text`), so that text inside templates, infoboxes, quotes, and side story resolutions is included. Convert it to Markdown with a script:

- Keep **all text**, including infobox fields, tables, quotes, trivia, and gameplay sections. Turn tables into Markdown tables or lists, and keep headings as headings.
- If the page has tabs (e.g. OT2 / Champions of the Continent), keep every tab, each under a heading `## [Tab] <tab name>`.
- Keep links to other wiki pages as `[link text](wiki:Exact Page Title)`. Stage 3 turns these into KB links.
- Drop only things that aren't text: images, galleries, `[edit]` links, the table of contents, navbox footers, and reference markers such as `[1]`.

Save each page as `kb_raw/pages/<slug>.md`:

```markdown
---
title: Frigit Isle: Entrance
slug: frigit_isle_entrance
verdict: ot2
reason: OT2 field location on Frigit Isle, part of Osvald's story
revid: 123456
---
<full page text>
```

**Slug rule:** lowercase, accents folded to ASCII, spaces → underscores, other punctuation dropped (`Throné` → `throne`). Slugs must be unique.

Write `kb_raw/pages/index.json`, which lists **every candidate** (including the `not_ot2` ones) with its title, slug, verdict, and reason.

## Step 4 — Check and report

Run these checks and paste their raw output into `preprocess/kb_1_report.md`:

1. Every `ot2` / `mixed` entry in `index.json` has a file, and every file has an entry.
2. No file's body is empty.
3. **Verdicts on these 10 pages:**
   - `ot2` or `mixed`: Osvald V. Vanstein, Agnea, New Delsta, Ku, Vide
   - `not_ot2`: Olberic Eisenberg, Cyrus Albright, Orsterra, plus 2 pages that are only about Champions of the Continent (name them)
4. **Nothing lost:** for 10 pages chosen at random, compare the saved text with the rendered page. Count the page's words that are missing from the saved file, not counting images, navboxes, and the table of contents. Report the count per page.
5. Counts: how many candidates, and how many `ot2`, `mixed`, and `not_ot2`.

The report also lists every `mixed` page, and every verdict you weren't sure about.

**Don't claim a check passed unless its output shows it.**

Only write inside `kb_raw/` and `preprocess/kb_1_report.md`.
