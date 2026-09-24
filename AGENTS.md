# AGENTS.md — story_engine (for Codex)

This is a Python CLI (`story-engine`) that generates Octopath Traveler II fan fiction using Claude agents. Each Goal Contract covers one roadmap step, and **the contract defines the scope**.

## Read first

Each Goal Contract starts a new session. Before writing any code, read:

- `docs/architecture.md` and `docs/tech_stacks.md`, in full. Your code has to fit this design, these libraries, and these Agent SDK patterns.
- Any other doc section the contract cites, such as prd's Style Specification.

Don't read `docs/roadmap.md` or `docs/history.md` unless the contract cites them. Your step is already in the contract, and the rest of those files is planning for other steps.

## Toolchain

- Python 3.12+ with **uv**. Run `uv sync` first, then run everything with `uv run ...`.
- Unit tests: `uv run pytest tests/unit`. They must pass before handoff, and they make no network or model calls.
- Live tests: `tests/e2e/` holds tests that call real models (pytest marker `e2e`). **Don't run them unless the contract explicitly allows it**, because every run costs money.
- CLI smoke check: `uv run story-engine --help`
- No linter or type checker is configured.

## Conventions

- **CLI:** Typer.
- **JSON artifacts:** Pydantic v2 models. Traces are append-only JSONL.
- **Run artifacts:** use the exact file names from the Run Directory section of `docs/architecture.md`, written under `runs/<run_id>/`.
- **Config:**
  - Model IDs and effort levels live only in `config/models.yaml`.
  - Tunables (word range, turn cap, validation rounds, default stop policy) live in `config/settings.yaml`.
  - Nothing is hard-coded.
- **LLM calls:**
  - Only through `claude-agent-sdk`, using persistent `ClaudeSDKClient` sessions. The shared setup goes in `src/story_engine/agents/sdk.py`.
  - Never use `anthropic`, `openai`, `langchain`, or `litellm`.
- **Agent file access:**
  - A PreToolUse hook enforces the rules. `kb/` is read-only, and writers may write only inside their own run directory.
  - A PostToolUse hook logs every `kb/` read to `retrieval.jsonl`.
- **Unit tests:** fake the SDK. Real API calls are not allowed in `tests/unit/`.

## Boundaries

- Touch only the files the contract needs. Don't refactor unrelated code.
- Don't add dependencies the contract doesn't allow. If you need one, stop and report it in the handoff.
- Don't edit `docs/`, `misc/`, `cards/`, or `eval/results/` unless the contract names them.
- Change `kb/` content only through the `story-engine kb` scripts.
- Never copy text from the novel files in `misc/` into any file.
- Never write secrets or credentials into files, and never write outside the repo.
- Don't commit or push. Git is handled outside your job.
