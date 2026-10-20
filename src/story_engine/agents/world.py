"""The world's persistent resolving session for one day."""

import json
from pathlib import Path
from typing import Self

from claude_agent_sdk import ClaudeSDKClient, ResultMessage
from pydantic import BaseModel, ConfigDict

from story_engine.agents.sdk import (
    KBHooks, SessionError, ThinkingUsage, json_object, session_error, session_options,
)
from story_engine.config import Role
from story_engine.trace import TraceWriter
from story_engine.world.io import validate_state
from story_engine.world.models import Event, WorldState


class Resolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[dict]
    state: dict
    situation_notes: dict[str, str]


class WorldAgent:
    def __init__(self, root: Path, run_dir: Path, world_dir: Path,
                 role: Role, max_turns: int, trace: TraceWriter) -> None:
        self.root, self.run_dir, self.world_dir = root, run_dir, world_dir
        self.role, self.max_turns, self.trace = role, max_turns, trace
        self.client = None
        self.opened = False
        self.turn = 0

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

    async def resolve(self, state: WorldState, choices: dict, events: list[Event]):
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        request = json.dumps({"state": state.model_dump(), "choices": choices,
                              "events": [event.model_dump() for event in events]}, ensure_ascii=False)
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
                resolved = []
                for raw in reply.events:
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
                    resolved.append(event)
                required = {s.id for s in state.situations if s.status == "open"}
                if required - reply.situation_notes.keys():
                    raise ValueError("situation_notes must cover every situation open at tick start")
                if any(not note.strip() for note in reply.situation_notes.values()):
                    raise ValueError("situation_notes must be non-empty sentences")
                return resolved, new_state, reply.situation_notes
            except ValueError as error:
                if attempt:
                    raise SessionError(f"World validation failed after one retry: {error}") from None
                request = f"World validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")
