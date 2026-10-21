<p align="center">
  <img src="assets/banner.svg" alt="Yet Another Story of Solistia" width="100%">
</p>

<p align="center"><b>English</b> · <a href="README.zh-CN.md">中文</a></p>

# Yet Another Story of Solistia

**Yet Another Story of Solistia** simulates the world of *Octopath Traveler II* after the true ending, and tells short stories from what happens in it.

Vide is defeated, and the eight travelers have finished their journeys. Here they go on living. Each traveler is played by its own agent, which acts on its own goals and memory. A World agent resolves what they attempt, plays everyone else, and keeps time. Nobody writes the plot. A curator picks the day's episode worth telling, and a narrator tells it, grounded in a knowledge base built from the game's wiki.

## How a story comes about

```
world new ─► Initializer: scene context from the KB + a starting world state
              (whereabouts, goals, commitments, small local troubles on a clock)
world run ─► one day, part by part (morning → night)
              ├─ each traveler chooses what to do with the part of the day
              ├─ the World resolves the choices and plays everyone else
              └─ where travelers meet, a scene plays out turn by turn
           ─► end of day: each traveler writes its memory; the world is saved
           ─► curator picks the episode → narrator tells it → validator checks it
```

The world persists: its event log is that world's canon, and a later run continues the same world for another day.

A `baseline` mode writes a story directly from the same starting world with a single strong model. The simulation has to tell stories at least as good as the baseline's to earn its keep.

## Status

A personal, work-in-progress project. Done so far: the knowledge base, the baseline writer, the evaluation kit, world creation, character and World agents, and turn-by-turn scenes. In progress: a full simulated day, then the curator, narrator, and validation.

## Quick start

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), and an Anthropic API key in `.env` (`ANTHROPIC_API_KEY=...`).

```bash
uv sync
uv run story-engine --help

# Create a world, then simulate its first day
uv run story-engine world new --characters agnea,throne --location cropdale \
  --situation "Agnea has brought Throné to a festival here."
uv run story-engine world run <world_id> --stop-after day

# A baseline story from the same kind of input
uv run story-engine generate --mode baseline --characters osvald,temenos \
  --location new_delsta --scenario "Osvald comes to town on scholarly business"

# Tests (unit tests make no model calls)
uv run pytest tests/unit
```

Commands that call a model cost money. Each run is capped by `max_cost_usd` in `config/settings.yaml`.

## Layout

| Path | What's there |
|---|---|
| `src/story_engine/` | CLI, agents, world model, simulation loop, evaluation tools |
| `prompts/`, `cards/` | Agent prompts and the eight travelers' identity cards |
| `kb/` | The knowledge base: Markdown files built from the wiki |
| `config/` | Models per role, and tunables such as the scene cap and cost cap |
| `eval/` | Fixed judge prompts and the test suite |
| `tests/` | Unit tests and live end-to-end tests |

## Disclaimer

An unofficial fan project, not affiliated with or endorsed by Square Enix. *Octopath Traveler* and all related names are trademarks of Square Enix. The knowledge base is derived from the [Octopath Traveler Fandom wiki](https://octopathtraveler.fandom.com/), whose text is licensed under [CC BY-SA](https://creativecommons.org/licenses/by-sa/3.0/). The banner is original artwork, not game art.
