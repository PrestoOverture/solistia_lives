"""The world's persistent resolving session for one day."""

import json
import re
import unicodedata
from pathlib import Path
from typing import Self

from claude_agent_sdk import ClaudeSDKClient, ResultMessage
from pydantic import BaseModel, ConfigDict, Field
import yaml

from story_engine.agents.sdk import (
    KBHooks, SessionCost, SessionError, ThinkingUsage, json_object, session_error, session_options,
)
from story_engine.config import Role
from story_engine.trace import TraceWriter
from story_engine.world.io import validate_state
from story_engine.world.models import Event, WorldState


def _fold(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value.casefold())
                   if not unicodedata.combining(char))


def _main_names(root: Path, characters) -> set[str]:
    names = set()
    for slug in characters:
        text = (root / "kb" / "characters" / slug / f"{slug}.md").read_text(encoding="utf-8")
        metadata = yaml.safe_load(text.split("---", 2)[1])
        names.update(_fold(name) for name in [metadata["name"], *metadata.get("aliases", [])])
        card = (root / "cards" / f"{slug}.md").read_text(encoding="utf-8")
        names.update(_fold(name.strip()) for name in re.findall(r"^# (.+)$", card, re.MULTILINE))
    return names


class Resolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[dict]
    state: dict
    situation_notes: dict[str, str] = Field(default_factory=dict)


class WorldAgent:
    def __init__(self, root: Path, run_dir: Path, world_dir: Path,
                 role: Role, max_turns: int, trace: TraceWriter) -> None:
        self.root, self.run_dir, self.world_dir = root, run_dir, world_dir
        self.role, self.max_turns, self.trace = role, max_turns, trace
        self.client = None
        self.opened = False
        self.seen: set[int] = set()
        self.turn = 0
        self.cost = SessionCost()

    async def __aenter__(self) -> Self:
        if self.opened:
            raise SessionError("WorldAgent context can only be opened once")
        self.opened = True
        prompt = "\n\n".join(path.read_text(encoding="utf-8") for path in (
            self.root / "prompts/world.md", self.world_dir / "scene_context.md"))
        self.hooks = KBHooks(self.root, self.run_dir, agent="world", turn=1)
        self.options = session_options(self.root, self.run_dir, self.role, prompt,
                                       self.max_turns, self.hooks)
        self.context = ClaudeSDKClient(options=self.options)
        self.client = await self.context.__aenter__()
        return self

    async def __aexit__(self, *args):
        try:
            return await self.context.__aexit__(*args)
        finally:
            self.client = None

    async def resolve(self, state: WorldState, choices: dict, events: list[Event], *,
                      scene_round: bool = False):
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        new_events = [event for event in events
                      if event.day == state.clock.day and event.id not in self.seen]
        self.seen.update(event.id for event in new_events)
        request = json.dumps({"state": state.model_dump(), "choices": choices,
                              "call": "scene_round" if scene_round else "part_of_day",
                              "events": [event.model_dump() for event in new_events]}, ensure_ascii=False)
        names = _main_names(self.root, state.characters)
        for attempt in range(2):
            thinking = ThinkingUsage()
            await self.client.query(request)
            result = None
            async for message in self.client.receive_response():
                self.hooks.observe(message)
                thinking.observe(message)
                if isinstance(message, ResultMessage):
                    self.trace.write("stage_usage", stage="world", agent="world", turn=self.turn,
                                     attempt=attempt + 1, usage=message.usage or {},
                                     num_turns=message.num_turns, total_cost_usd=message.total_cost_usd,
                        call_cost_usd=self.cost.delta(message.total_cost_usd),
                                     thinking_blocks=thinking.thinking_blocks,
                                     thinking_chars=thinking.thinking_chars)
                    if message.is_error or message.subtype != "success":
                        raise session_error(f"World session {message.subtype}: " +
                                            ("; ".join(message.errors or []) or message.result or "unspecified SDK error"), self.options.env)
                    result = message.result
            try:
                if result is None:
                    raise ValueError("world session returned no final text")
                reply = Resolution.model_validate(json_object(result))
                if "clock" in reply.state:
                    raise ValueError("World state must omit clock")
                new_state = validate_state(self.world_dir, WorldState.model_validate(
                    {**reply.state, "clock": state.clock.model_dump()}))
                if scene_round:
                    for slug, character in state.characters.items():
                        if (choices.get(slug, {}).get("move") != "leave"
                                and new_state.characters[slug].where != character.where):
                            raise ValueError(f"M1 where-lock: {slug} did not leave; where must remain {character.where!r}")
                resolved = []
                for index, raw in enumerate(reply.events):
                    event = Event.model_validate({"id": 0, **state.clock.model_dump(), **raw})
                    if {"id", "day", "part"} & raw.keys():
                        raise ValueError("event id/day/part are assigned by code")
                    if event.actor in state.characters:
                        raise ValueError("World event actor must not be a main character")
                    if event.intent is not None:
                        raise ValueError("World event intent must be null")
                    if event.place not in {place.slug for place in new_state.places}:
                        raise ValueError("World event place must be in new state's places")
                    if set(event.perceived_by) - state.characters.keys():
                        raise ValueError("perceived_by must contain only main characters")
                    unquoted = re.sub(r'"[^"]*"|“[^”]*”', '', event.content)
                    for sentence in re.split(r'(?<=[.!?])\s+|\n+', unquoted):
                        start = _fold(sentence.lstrip(' \t\r\"“”‘’'))
                        if any(re.match(re.escape(name) + r"(?!\w)", start) for name in names):
                            raise ValueError(f"M2 subject check: event index {index}, sentence {sentence!r} begins with a main character name or alias")
                    resolved.append(event)
                required = {s.id for s in state.situations if s.status == "open"}
                if not scene_round and required - reply.situation_notes.keys():
                    raise ValueError("situation_notes must cover every situation open at tick start")
                if any(not note.strip() for note in reply.situation_notes.values()):
                    raise ValueError("situation_notes must be non-empty sentences")
                return resolved, new_state, reply.situation_notes
            except ValueError as error:
                self.trace.write("world_validation_failed", error=str(error), raw_reply=result,
                                 turn=self.turn, attempt=attempt + 1)
                if attempt:
                    raise SessionError(f"World validation failed after one retry: {error}") from None
                request = f"World validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")
