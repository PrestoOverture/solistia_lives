# KB Stage 3 — Link

`kb/` holds the polished lore files. Their links still point at the wiki: `[text](wiki:Page Title)`. Turn them into links between KB files.

**First, three small fixes:**

1. Rename `kb/characters/claude.md` to `claude_blacksnakes.md` and set `name: claude_blacksnakes`. A file named `claude.md` gets mistaken for a tool config file.
2. `order_of_blood`, `moonshade_order`, and `cateracta` each exist in two directories. Merge each pair into one file.
3. Where `aliases` is empty, fill it with the wiki title from `source`.

**Then link, with a script:**

- Map every wiki title to its KB file, using each file's `source` and `aliases`.
- `[text](wiki:Title)` becomes `[text](relative/path.md)` if Title maps to a KB file. Otherwise it becomes plain `text`.
- Change nothing else in the text.

Only write inside `kb/`.
