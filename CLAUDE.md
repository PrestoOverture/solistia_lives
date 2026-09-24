# CLAUDE.md — Solistia Lives (story_engine)

This project generates short fiction set after the true ending of Octopath Traveler II, using four kinds of agents: a Director, character agents, a narrator, and a validator. Implementation follows `docs/roadmap.md`.

## Docs (source of truth)


| File                   | What it holds                                                               |
| ---------------------- | --------------------------------------------------------------------------- |
| `docs/prd.md`          | Product scope, style spec, success metrics                                  |
| `docs/architecture.md` | Design, repo layout, run directory, CLI, Key Decisions (D#), open questions |
| `docs/tech_stacks.md`  | Stack, models, how the Claude Agent SDK is used                             |
| `docs/roadmap.md`      | Unfinished MVP steps (Do / Test)                                            |
| `docs/history.md`      | Log of what was done and decided, newest entry first                        |
| `misc/non_mvp.md`      | Everything beyond the MVP                                                   |


Each topic lives in exactly one file. Link to it instead of repeating it, and keep the docs lean.

## Session start

Read `docs/prd.md`, `docs/architecture.md`, `docs/tech_stacks.md`, and `docs/roadmap.md` in full, plus the latest entry in `docs/history.md`. `roadmap.md` holds only the unfinished phases, so its first phase is the current one. Read older history entries and `misc/non_mvp.md` only when a task needs them.

## Implementation

- Codex writes the code, through the **c2c-workflow MCP** (`codex`). When the user asks for it, use the **c2c-lite** skill (`/c2c-lite`) instead. How to use each one is covered in the MCP's instructions and the skill.
- Each contract covers one roadmap step, and that step's **Test** line becomes the Success Conditions. Review results against `AGENTS.md` and the Repository Structure, Run Directory, and CLI sections of `docs/architecture.md`.
- Every contract starts a fresh Codex session, and Codex reads only `architecture.md` and `tech_stacks.md` on its own. So each contract must cite any other doc section the step needs (e.g. prd's Style Specification), and give file paths for anything it uses from earlier steps.

## After work

- After any experiment or decision, add an entry to `docs/history.md`.
- When a phase's Phase test passes:
  1. Record the results and the artifact paths in `docs/history.md`.
  2. Delete that phase from `docs/roadmap.md`.
  3. Repoint any later step that referenced the deleted phase to the artifact files. For example, 3.10's "baseline story … from 2.7" becomes `eval/results/baseline_v1.md` and its run dirs.
- If a decision changes, update the D-table in `docs/architecture.md` and log the change in `docs/history.md`.

## Don't

- Don't run 💰 commands (anything that calls a real model, which costs money) without the user's approval.
- Don't hand-edit `kb/` content. It changes only through the `story-engine kb` scripts or the user's review.
- Don't edit `misc/`. It is reference material. Never copy text from the novel into prompts, the KB, cards, or stories.

