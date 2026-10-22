"""The narrator's single draft-writing session."""

import json
from pathlib import Path

from claude_agent_sdk import ClaudeSDKClient, ResultMessage

from story_engine.agents.curator import Episode
from story_engine.agents.sdk import KBHooks, SessionCost, SessionError, session_error, session_options
from story_engine.config import Role, Words
from story_engine.runs import record_api_host
from story_engine.trace import TraceWriter
from story_engine.world.models import Event, SceneRecord

ACT_FILENAME = "act_1.md"  # 3.8 narrates only the first act; later acts come in 3.8b.


def _event_row(event: Event, pov: str) -> dict:
    row = event.model_dump(include={"id", "part", "place", "actor", "type", "content"})
    row["intent"] = event.intent if event.actor == pov else None
    return row


def episode_events(events: list[Event], scenes: list[SceneRecord], episode: Episode) -> list[Event]:
    """The chosen scenes' events, plus the part-of-day events between them, in order."""
    by_id = {scene.id: scene for scene in scenes}
    chosen = [by_id[scene_id] for scene_id in episode.scenes]
    first_id = min(scene.first_event_id for scene in chosen)
    last_id = max(scene.last_event_id for scene in chosen)
    chosen_ids = set(episode.scenes)
    return [
        event for event in events
        if event.scene in chosen_ids or (event.scene is None and first_id <= event.id <= last_id)
    ]


def act_scene_events(events: list[Event], scene_id: str) -> list[Event]:
    """This act's scene events, in order."""
    return [event for event in events if event.scene == scene_id]


def act_transition_events(events: list[Event], scenes: list[SceneRecord], scene: SceneRecord) -> list[Event]:
    """The part-of-day events since the previous act: this step, since the previous scene of the
    same day (or the start of the day, if this is the day's first scene) up to this scene's start."""
    day_scenes = sorted((other for other in scenes if other.day == scene.day), key=lambda other: other.first_event_id)
    index = next(i for i, other in enumerate(day_scenes) if other.id == scene.id)
    previous = day_scenes[index - 1] if index > 0 else None
    lower = previous.last_event_id if previous is not None else 0
    return [
        event for event in events
        if event.scene is None and event.day == scene.day and lower < event.id < scene.first_event_id
    ]


async def narrate_act(
    root: Path, run_dir: Path, events: list[Event], scenes: list[SceneRecord], scene: SceneRecord,
    pov: str, characters: list[str], role: Role, act_words: Words, max_turns: int, trace: TraceWriter,
) -> None:
    """Narrate one act (one scene) into runs/<run_id>/acts/act_1.md."""
    hooks = KBHooks(root, run_dir, agent="narrator", turn=0)
    sources = [
        root / "prompts/narrator.md",
        root / "prompts/style_spec.md",
        *(root / "cards" / f"{slug}.md" for slug in characters),
    ]
    prompt = "\n\n".join(path.read_text(encoding="utf-8") for path in sources)
    prompt += "\n\n# Scene context\n\n" + (run_dir / "scene_context.md").read_text(encoding="utf-8")
    options = session_options(root, run_dir, role, prompt, max_turns, hooks, tools=["Read"])
    record_api_host(run_dir, options.env.get("ANTHROPIC_BASE_URL"))
    request = json.dumps(
        {
            "pov": pov,
            "scene_events": [_event_row(event, pov) for event in act_scene_events(events, scene.id)],
            "part_of_day_events": [
                _event_row(event, pov) for event in act_transition_events(events, scenes, scene)
            ],
            "previous_acts": [],
            "words": act_words.model_dump(),
        },
        ensure_ascii=False,
    )
    cost = SessionCost()
    acts_dir = run_dir / "acts"
    async with ClaudeSDKClient(options=options) as client:
        await client.query(request)
        async for message in client.receive_response():
            hooks.observe(message)
            if isinstance(message, ResultMessage):
                trace.write(
                    "stage_usage", stage="narrate_act", agent="narrator",
                    usage=message.usage or {}, num_turns=message.num_turns,
                    total_cost_usd=message.total_cost_usd,
                    call_cost_usd=cost.delta(message.total_cost_usd),
                )
                if message.is_error or message.subtype != "success":
                    raise session_error(
                        f"Narrator session {message.subtype}: "
                        + ("; ".join(message.errors or []) or message.result or "unspecified SDK error"),
                        options.env,
                    )
                if not message.result or not message.result.strip():
                    raise SessionError("Narrator session returned no final text")
                acts_dir.mkdir(exist_ok=True)
                (acts_dir / ACT_FILENAME).write_text(message.result, encoding="utf-8")
                return
    raise SessionError("Narrator session ended without a result")


async def narrate(
    root: Path, run_dir: Path, events: list[Event], scenes: list[SceneRecord], episode: Episode,
    characters: list[str], role: Role, words: Words, max_turns: int, trace: TraceWriter,
) -> None:
    hooks = KBHooks(root, run_dir, agent="narrator", turn=0)
    sources = [
        root / "prompts/narrator.md",
        root / "prompts/style_spec.md",
        *(root / "cards" / f"{slug}.md" for slug in characters),
    ]
    prompt = "\n\n".join(path.read_text(encoding="utf-8") for path in sources)
    prompt += "\n\n# Scene context\n\n" + (run_dir / "scene_context.md").read_text(encoding="utf-8")
    options = session_options(root, run_dir, role, prompt, max_turns, hooks, tools=["Read"])
    record_api_host(run_dir, options.env.get("ANTHROPIC_BASE_URL"))
    payload = [_event_row(event, episode.pov) for event in episode_events(events, scenes, episode)]
    request = json.dumps(
        {"pov": episode.pov, "events": payload, "words": words.model_dump()}, ensure_ascii=False,
    )
    cost = SessionCost()
    async with ClaudeSDKClient(options=options) as client:
        await client.query(request)
        async for message in client.receive_response():
            hooks.observe(message)
            if isinstance(message, ResultMessage):
                trace.write(
                    "stage_usage", stage="narrate", agent="narrator",
                    usage=message.usage or {}, num_turns=message.num_turns,
                    total_cost_usd=message.total_cost_usd,
                    call_cost_usd=cost.delta(message.total_cost_usd),
                )
                if message.is_error or message.subtype != "success":
                    raise session_error(
                        f"Narrator session {message.subtype}: "
                        + ("; ".join(message.errors or []) or message.result or "unspecified SDK error"),
                        options.env,
                    )
                if not message.result or not message.result.strip():
                    raise SessionError("Narrator session returned no final text")
                (run_dir / "draft.md").write_text(message.result, encoding="utf-8")
                return
    raise SessionError("Narrator session ended without a result")
