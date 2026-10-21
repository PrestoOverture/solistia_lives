"""Select an episode (one or more scenes) from one completed day's events."""

import json
from pathlib import Path

from claude_agent_sdk import ClaudeSDKClient, ResultMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator

from story_engine.agents.sdk import (
    KBHooks, SessionCost, SessionError, json_schema_output, session_error, session_options,
    structured_reply,
)
from story_engine.config import Role
from story_engine.runs import record_api_host
from story_engine.kb import normalize_slug
from story_engine.trace import TraceWriter
from story_engine.world.models import Event, SceneRecord


class Episode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenes: list[str] = Field(min_length=1)
    pov: str
    why: str

    @field_validator("pov")
    @classmethod
    def pov_slug(cls, value: str) -> str:
        return normalize_slug(value)  # the model may write "Throné" for the slug "throne"


def validate_episode(episode: Episode, scenes: list[SceneRecord], characters: list[str]) -> Episode:
    by_id = {scene.id: scene for scene in scenes}
    if len(set(episode.scenes)) != len(episode.scenes):
        raise ValueError("scenes must not repeat")
    unknown = [scene_id for scene_id in episode.scenes if scene_id not in by_id]
    if unknown:
        raise ValueError(f"unknown scene id(s) for this day: {', '.join(unknown)}")
    order = {scene.id: index for index, scene in enumerate(sorted(scenes, key=lambda scene: scene.first_event_id))}
    indices = [order[scene_id] for scene_id in episode.scenes]
    if indices != sorted(indices):
        raise ValueError("scenes must be listed in chronological order")
    if episode.pov not in characters:
        # A full name such as "Throné Anguis" folds to "throne_anguis"; match its first-name slug.
        matches = [slug for slug in characters if slug in episode.pov.split("_")]
        if len(matches) != 1:
            raise ValueError(f"pov {episode.pov!r} must be a main character slug: {', '.join(characters)}")
        episode = episode.model_copy(update={"pov": matches[0]})
    chosen = [by_id[scene_id] for scene_id in episode.scenes]
    if not any(episode.pov in scene.participants for scene in chosen):
        raise ValueError("pov must be a participant of at least one chosen scene")
    return episode


def _event_row(event: Event, characters: list[str]) -> dict:
    row = event.model_dump(include={"id", "part", "place", "actor", "type", "content"})
    if event.actor in characters:
        row["intent"] = event.intent
    return row


def _build_payload(events: list[Event], scenes: list[SceneRecord], characters: list[str]) -> list[dict]:
    """Interleave each scene (with all its events) with the day's part-of-day events, in order."""
    by_id = {scene.id: scene for scene in scenes}
    seen: set[str] = set()
    payload = []
    for event in events:
        if event.scene is None:
            payload.append(_event_row(event, characters))
            continue
        if event.scene in seen:
            continue
        seen.add(event.scene)
        scene = by_id[event.scene]
        scene_events = [other for other in events if other.scene == scene.id]
        payload.append({
            "scene": scene.id, "part": scene.part, "place": scene.place,
            "participants": scene.participants, "rounds": scene.rounds, "end": scene.end,
            "events": [_event_row(other, characters) for other in scene_events],
        })
    return payload


async def curate(
    root: Path, run_dir: Path, events: list[Event], scenes: list[SceneRecord], characters: list[str],
    role: Role, max_turns: int, trace: TraceWriter,
) -> Episode:
    hooks = KBHooks(root, run_dir, "curator", 1)
    options = session_options(root, run_dir, role,
                              (root / "prompts/curator.md").read_text(encoding="utf-8"),
                              max_turns, hooks, tools=[], output_format=json_schema_output(Episode))
    record_api_host(run_dir, options.env.get("ANTHROPIC_BASE_URL"))
    payload = _build_payload(events, scenes, characters)
    request = json.dumps({"characters": characters, "events": payload,
                          "reply": "JSON {scenes, pov, why}"}, ensure_ascii=False)
    cost = SessionCost()
    async with ClaudeSDKClient(options=options) as client:
        for attempt in range(2):
            await client.query(request)
            result = None
            structured_output = None
            async for message in client.receive_response():
                if isinstance(message, ResultMessage):
                    trace.write("stage_usage", stage="curate", agent="curator", attempt=attempt + 1,
                                usage=message.usage or {}, num_turns=message.num_turns,
                                total_cost_usd=message.total_cost_usd,
                                call_cost_usd=cost.delta(message.total_cost_usd))
                    if message.is_error or message.subtype != "success":
                        raise session_error(f"Curator session {message.subtype}: "
                                            + ("; ".join(message.errors or []) or message.result or "unspecified SDK error"), options.env)
                    result = message.result
                    structured_output = message.structured_output
            try:
                episode = validate_episode(
                    Episode.model_validate(structured_reply(result, structured_output)), scenes, characters)
            except ValueError as error:
                if attempt:
                    raise SessionError(f"Curator validation failed after one retry: {error}") from None
                request = f"Reply validation failed: {error}\nReturn corrected JSON."
                continue
            (run_dir / "episode.json").write_text(episode.model_dump_json(indent=2), encoding="utf-8")
            return episode
    raise AssertionError("unreachable")
