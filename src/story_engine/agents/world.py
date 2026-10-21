"""The world's persistent resolving session for one day."""

import json
from pathlib import Path
from typing import Annotated, Literal, Self, Union

from claude_agent_sdk import ClaudeSDKClient, ResultMessage
from pydantic import BaseModel, ConfigDict, Field, model_validator

from story_engine.agents.sdk import (
    KBHooks, SessionCost, SessionError, ThinkingUsage, json_schema_output, session_error,
    session_options, structured_reply,
)
from story_engine.agents.subjects import main_names, sentences, starts_with_name
from story_engine.config import Role
from story_engine.trace import TraceWriter
from story_engine.world.io import validate_state
from story_engine.world.models import Event, WorldState


class PartResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call: Literal["part_of_day"]
    events: list[dict]
    state: dict
    situation_notes: dict[str, str] = Field(default_factory=dict)
    encounters: list[dict] = Field(default_factory=list)


class Encounter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    place: str
    minor: list[str] = Field(default_factory=list)


class MinorMove(BaseModel):
    """A minor participant's move: the same shape as a character's Action, minus intent."""

    model_config = ConfigDict(extra="forbid")
    move: Literal["act", "wait", "leave"]
    urge: int = 0
    to: str | None = None
    action: str = ""
    say: str = ""

    @model_validator(mode="after")
    def valid_move(self) -> Self:
        if self.move == "act":
            if not 1 <= self.urge <= 3:
                raise ValueError("act urge must be 1-3")
            if not (self.action.strip() or self.say.strip()):
                raise ValueError("act needs a non-empty action or say")
        elif self.urge != 0:
            raise ValueError("wait and leave urge must be 0")
        return self


class RoundResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call: Literal["scene_round"]
    outcome: dict | None = None
    minor_moves: dict[str, MinorMove] = Field(default_factory=dict)


WorldReply = Annotated[Union[PartResolution, RoundResolution], Field(discriminator="call")]


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
                                       self.max_turns, self.hooks,
                                       output_format=json_schema_output(WorldReply))
        self.context = ClaudeSDKClient(options=self.options)
        self.client = await self.context.__aenter__()
        return self

    async def __aexit__(self, *args):
        try:
            return await self.context.__aexit__(*args)
        finally:
            self.client = None

    def _new_events(self, state: WorldState, events: list[Event]) -> list[Event]:
        new_events = [event for event in events
                      if event.day == state.clock.day and event.id not in self.seen]
        self.seen.update(event.id for event in new_events)
        return new_events

    async def _send(self, request: str):
        """Send one query and return (result_text, trace_fields) for the final reply."""
        thinking = ThinkingUsage()
        await self.client.query(request)
        result = None
        structured_output = None
        usage_fields = None
        async for message in self.client.receive_response():
            self.hooks.observe(message)
            thinking.observe(message)
            if isinstance(message, ResultMessage):
                usage_fields = dict(
                    usage=message.usage or {}, num_turns=message.num_turns,
                    total_cost_usd=message.total_cost_usd,
                    call_cost_usd=self.cost.delta(message.total_cost_usd),
                    thinking_blocks=thinking.thinking_blocks, thinking_chars=thinking.thinking_chars,
                )
                if message.is_error or message.subtype != "success":
                    raise session_error(f"World session {message.subtype}: " +
                                        ("; ".join(message.errors or []) or message.result or "unspecified SDK error"),
                                        self.options.env)
                result = message.result
                structured_output = message.structured_output
        return result, structured_output, usage_fields

    def _build_event(self, raw: dict, state: WorldState, places: set[str],
                     names: set[str], valid_of: set[str]) -> Event:
        if {"id", "day", "part", "scene"} & raw.keys():
            raise ValueError("event id/day/part/scene are assigned by code")
        event = Event.model_validate({"id": 0, **state.clock.model_dump(), **raw})
        if event.actor in state.characters:
            raise ValueError("World event actor must not be a main character")
        if event.intent is not None:
            raise ValueError("World event intent must be null")
        if event.place not in places:
            raise ValueError("World event place must be in new state's places")
        if set(event.perceived_by) - state.characters.keys():
            raise ValueError("perceived_by must contain only main characters")
        if event.of is not None and event.of not in valid_of:
            raise ValueError("World event of must name a main character whose attempt this call resolves")
        if event.type != "speech":
            check_names = (main_names(self.root, (slug for slug in state.characters if slug != event.of))
                          if event.of is not None else names)
            for sentence in sentences(event.content):
                if starts_with_name(sentence, check_names):
                    raise ValueError(f"M2 subject check: sentence {sentence!r} begins with a main character name or alias")
        return event

    async def resolve(self, state: WorldState, choices: dict, events: list[Event]):
        """Part-of-day resolution: settle off-screen life and return the encounters."""
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        new_events = self._new_events(state, events)
        request = json.dumps({"state": state.model_dump(), "choices": choices,
                              "call": "part_of_day",
                              "events": [event.model_dump() for event in new_events]}, ensure_ascii=False)
        names = main_names(self.root, state.characters)
        for attempt in range(2):
            result, structured_output, usage_fields = await self._send(request)
            if usage_fields is not None:
                self.trace.write("stage_usage", stage="world", agent="world", turn=self.turn,
                                 attempt=attempt + 1, **usage_fields)
            try:
                reply = PartResolution.model_validate(structured_reply(result, structured_output))
                if "clock" in reply.state:
                    raise ValueError("World state must omit clock")
                new_state = validate_state(self.world_dir, WorldState.model_validate(
                    {**reply.state, "clock": state.clock.model_dump()}))
                valid_of = set(choices.keys()) & state.characters.keys()
                places = {place.slug for place in new_state.places}
                resolved = [self._build_event(raw, state, places, names, valid_of) for raw in reply.events]
                required = {s.id for s in state.situations if s.status == "open"}
                if required - reply.situation_notes.keys():
                    raise ValueError("situation_notes must cover every situation open at tick start")
                if any(not note.strip() for note in reply.situation_notes.values()):
                    raise ValueError("situation_notes must be non-empty sentences")
                encounters = []
                for raw in reply.encounters:
                    encounter = Encounter.model_validate(raw)
                    if encounter.place not in places:
                        raise ValueError("encounter place must be in state places")
                    if not any(character.where == encounter.place for character in new_state.characters.values()):
                        raise ValueError("encounter place must have at least one main character there")
                    encounters.append(encounter)
                return resolved, new_state, reply.situation_notes, encounters
            except ValueError as error:
                self.trace.write("world_validation_failed", error=str(error), raw_reply=result,
                                 turn=self.turn, attempt=attempt + 1)
                if attempt:
                    raise SessionError(f"World validation failed after one retry: {error}") from None
                request = f"World validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")

    async def round(self, state: WorldState, events: list[Event],
                    *, place: str, main_present: list[str], minor_present: list[str],
                    last_winner: dict | None):
        """One scene round: the previous winning move's outcome, and this round's minor moves."""
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        new_events = self._new_events(state, events)
        request = json.dumps({"state": state.model_dump(), "call": "scene_round",
                              "place": place, "participants": {"main": main_present, "minor": minor_present},
                              "last_winner": last_winner,
                              "events": [event.model_dump() for event in new_events]}, ensure_ascii=False)
        names = main_names(self.root, state.characters)
        places = {place.slug for place in state.places}
        for attempt in range(2):
            result, structured_output, usage_fields = await self._send(request)
            if usage_fields is not None:
                self.trace.write("stage_usage", stage="world", agent="world", turn=self.turn,
                                 attempt=attempt + 1, **usage_fields)
            try:
                reply = RoundResolution.model_validate(structured_reply(result, structured_output))
                valid_of = ({last_winner["actor"]} if last_winner is not None
                           and last_winner.get("actor") in state.characters else set())
                outcome = (self._build_event(reply.outcome, state, places, names, valid_of)
                          if reply.outcome is not None else None)
                minor_moves = {}
                for name, move in reply.minor_moves.items():
                    for sentence in sentences(move.action):
                        if starts_with_name(sentence, names):
                            raise ValueError(f"M2 subject check: minor {name!r} action {sentence!r} begins with a main character name or alias")
                    minor_moves[name] = move
                return outcome, minor_moves
            except ValueError as error:
                self.trace.write("world_validation_failed", error=str(error), raw_reply=result,
                                 turn=self.turn, attempt=attempt + 1)
                if attempt:
                    raise SessionError(f"World validation failed after one retry: {error}") from None
                request = f"World validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")
