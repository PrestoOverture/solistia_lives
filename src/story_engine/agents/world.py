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
from story_engine.config import Role
from story_engine.agents.subjects import fold
from story_engine.trace import TraceWriter
from story_engine.world.io import save_state, validate_state
from story_engine.world.models import Event, Person, Place, Situation, WorldState


class WorldEvent(BaseModel):
    """A World-written event as it appears in a scene_round reply; code assigns id, time,
    scene, and round."""
    model_config = ConfigDict(extra="forbid")
    place: str
    actor: str
    type: Literal["speech", "action", "world", "state_change"]
    content: str = Field(max_length=280)
    of: str | None = None
    intent: str | None = None
    perceived_by: list[str] = Field(default_factory=list)


class OffscreenEvent(BaseModel):
    """An off-screen event: no `of` (off-screen life never resolves a main character's
    attempt) and no `perceived_by` (code computes it from who is at `place`/`spot`)."""
    model_config = ConfigDict(extra="forbid")
    place: str
    actor: str
    type: Literal["speech", "action", "world", "state_change"]
    content: str = Field(max_length=280)
    intent: str | None = None
    spot: str | None = None


class Settled(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["settled"]
    outcome: str = Field(max_length=280)
    where: str
    spot: str | None = None


class Staged(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["staged"]
    where: str
    spot: str | None = None


Verdict = Annotated[Union[Settled, Staged], Field(discriminator="status")]


class Encounter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mains: list[str] = Field(min_length=1)
    minor: list[str] = Field(default_factory=list)


class AdjudicateReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call: Literal["adjudicate"]
    verdicts: dict[str, Verdict]
    encounters: list[dict] = Field(default_factory=list)


class OffscreenReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call: Literal["offscreen"]
    events: list[OffscreenEvent] = Field(default_factory=list)
    people: dict[str, Person] = Field(default_factory=dict)
    situations: list[Situation] = Field(default_factory=list)
    places: list[Place] = Field(default_factory=list)
    situation_notes: dict[str, str] = Field(default_factory=dict)


class MinorMove(BaseModel):
    """A minor participant's move: the same shape as a character's Action, minus intent."""

    model_config = ConfigDict(extra="forbid")
    move: Literal["act", "wait", "leave"]
    urge: int = 0
    to: str | None = None
    action: str = Field(default="", max_length=180)
    say: str = Field(default="", max_length=400)

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
    outcome: WorldEvent | None = None
    minor_moves: dict[str, MinorMove] = Field(default_factory=dict)
    new_people: dict[str, Person] = Field(default_factory=dict)


WorldReply = Annotated[Union[AdjudicateReply, OffscreenReply, RoundResolution],
                       Field(discriminator="call")]


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

    def _build_event(self, raw: "WorldEvent", state: WorldState, places: set[str], valid_of: set[str]) -> Event:
        event = Event.model_validate({"id": 0, **state.clock.model_dump(), **raw.model_dump()})
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
        return event

    def _build_offscreen_event(self, raw: "OffscreenEvent", state: WorldState, places: set[str]) -> Event:
        data = raw.model_dump()
        spot = data.pop("spot", None)
        event = Event.model_validate({"id": 0, **state.clock.model_dump(), **data,
                                      "of": None, "perceived_by": []})
        if event.actor in state.characters:
            raise ValueError("World event actor must not be a main character")
        if event.intent is not None:
            raise ValueError("World event intent must be null")
        if event.place not in places:
            raise ValueError("World event place must be in places")
        perceived_by = [slug for slug, character in state.characters.items()
                        if character.where == event.place and (spot is None or character.spot == spot)]
        return event.model_copy(update={"perceived_by": perceived_by})

    async def adjudicate(self, state: WorldState, choices: dict, events: list[Event]):
        """Adjudicate call: settle or stage each main character's plan, and the encounters."""
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        new_events = self._new_events(state, events)
        request = json.dumps({"state": state.model_dump(), "choices": choices,
                              "call": "adjudicate",
                              "events": [event.model_dump() for event in new_events]}, ensure_ascii=False)
        valid_of = set(choices.keys()) & state.characters.keys()
        places = {place.slug for place in state.places}
        for attempt in range(2):
            result, structured_output, usage_fields = await self._send(request)
            if usage_fields is not None:
                self.trace.write("stage_usage", stage="world", agent="world", turn=self.turn,
                                 attempt=attempt + 1, **usage_fields)
            try:
                reply = AdjudicateReply.model_validate(structured_reply(result, structured_output))
                if set(reply.verdicts.keys()) != valid_of:
                    raise ValueError("verdicts must cover exactly the main characters who planned this tick")
                for slug, verdict in reply.verdicts.items():
                    if verdict.where not in places:
                        raise ValueError(f"{slug}'s verdict where must name a place slug")
                encounters = []
                for raw in reply.encounters:
                    encounter = Encounter.model_validate(raw)
                    if set(encounter.mains) - reply.verdicts.keys():
                        raise ValueError("encounter mains must be main characters with a verdict this call")
                    whereabouts = {slug: (reply.verdicts[slug].where, reply.verdicts[slug].spot)
                                  for slug in encounter.mains}
                    if len(set(whereabouts.values())) > 1:
                        raise ValueError(
                            "encounter mains must share one place and spot, but "
                            + ", ".join(f"{slug} is at {where!r}" for slug, where in whereabouts.items()))
                    encounters.append(encounter)
                return reply.verdicts, encounters
            except ValueError as error:
                self.trace.write("world_validation_failed", error=str(error), raw_reply=result,
                                 turn=self.turn, attempt=attempt + 1)
                if attempt:
                    raise SessionError(f"World validation failed after one retry: {error}") from None
                request = f"World validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")

    async def offscreen(self, state: WorldState, outcomes: list[str], open_situations: set[str]):
        """Off-screen call: given places, people, situations, and the adjudicated outcomes'
        text (never a main character's plan or intent), write what everyone else does."""
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        request = json.dumps({"call": "offscreen", "clock": state.clock.model_dump(),
                              "places": [place.model_dump() for place in state.places],
                              "people": {name: person.model_dump() for name, person in state.people.items()},
                              "situations": [situation.model_dump() for situation in state.situations],
                              "outcomes": outcomes}, ensure_ascii=False)
        for attempt in range(2):
            result, structured_output, usage_fields = await self._send(request)
            if usage_fields is not None:
                self.trace.write("stage_usage", stage="world", agent="world", turn=self.turn,
                                 attempt=attempt + 1, **usage_fields)
            try:
                reply = OffscreenReply.model_validate(structured_reply(result, structured_output))
                # People persist (D21): the reply updates or adds people; anyone it omits is kept.
                people = {name: person.model_dump() for name, person in state.people.items()}
                people.update({name: person.model_dump() for name, person in reply.people.items()})
                new_state = validate_state(self.world_dir, WorldState.model_validate({
                    "clock": state.clock.model_dump(),
                    "places": [place.model_dump() for place in reply.places],
                    "characters": {slug: character.model_dump() for slug, character in state.characters.items()},
                    "people": people,
                    "situations": [situation.model_dump() for situation in reply.situations],
                }))
                places = {place.slug for place in new_state.places}
                resolved = [self._build_offscreen_event(raw, new_state, places) for raw in reply.events]
                if open_situations - reply.situation_notes.keys():
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

    async def resolve(self, state: WorldState, choices: dict, events: list[Event]):
        """Part-of-day resolution, in two calls (D28): adjudicate the plans, then write
        off-screen life. Code applies the verdicts in between: it writes each settled
        outcome's event, moves every verdicted main character, and opens a solo attempt
        scene for any staged character left out of an encounter."""
        verdicts, encounters = await self.adjudicate(state, choices, events)
        characters = dict(state.characters)
        for slug, verdict in verdicts.items():
            characters[slug] = characters[slug].model_copy(
                update={"where": verdict.where, "spot": verdict.spot})
        moved_state = validate_state(self.world_dir, state.model_copy(update={"characters": characters}))
        outcome_events = []
        for slug, verdict in verdicts.items():
            if verdict.status == "settled":
                perceived_by = [other for other, character in characters.items()
                                if (character.where, character.spot) == (verdict.where, verdict.spot)]
                outcome_events.append(Event(
                    id=0, **state.clock.model_dump(), place=verdict.where, actor="world", of=slug,
                    type="world", content=verdict.outcome, perceived_by=perceived_by))
        encountered_mains = {slug for encounter in encounters for slug in encounter.mains}
        for slug, verdict in verdicts.items():
            if verdict.status == "staged" and slug not in encountered_mains:
                encounters.append(Encounter(mains=[slug], minor=[]))
        open_situations = {situation.id for situation in state.situations if situation.status == "open"}
        outcomes = [verdict.outcome for verdict in verdicts.values() if verdict.status == "settled"]
        off_events, new_state, situation_notes = await self.offscreen(moved_state, outcomes, open_situations)
        statuses = {slug: verdict.status for slug, verdict in verdicts.items()}
        return outcome_events + off_events, new_state, situation_notes, encounters, statuses

    async def round(self, state: WorldState, events: list[Event],
                    *, place: str, main_present: list[str], minor_present: list[str],
                    last_winner: dict | None):
        """One scene round: the previous winning move's outcome, this round's minor moves, and
        any new_people the World brings into the scene — the only state change a round may make."""
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        new_events = self._new_events(state, events)
        minor_people = {name: state.people[name].model_dump()
                       for name in minor_present if name in state.people}
        request = json.dumps({"state": state.model_dump(), "call": "scene_round",
                              "place": place, "participants": {"main": main_present, "minor": minor_present},
                              "people": minor_people,
                              "last_winner": last_winner,
                              "events": [event.model_dump() for event in new_events]}, ensure_ascii=False)
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
                outcome = (self._build_event(reply.outcome, state, places, valid_of)
                          if reply.outcome is not None else None)
                minor_moves = {}
                # People are data references: match names ignoring case, accents, spaces/underscores.
                keys = {_key(existing): existing for existing in state.people}
                for name, move in reply.minor_moves.items():
                    if name not in reply.new_people:
                        name = keys.get(_key(name), name)
                        person = state.people.get(name)
                        if person is None or person.where != place:
                            raise ValueError(
                                f"minor_moves name {name!r} must be a people entry at this place, "
                                f"or in this round's new_people (people here: "
                                f"{sorted(n for n, p in state.people.items() if p.where == place)})")
                    minor_moves[name] = move
                new_state = state
                if reply.new_people:
                    new_state = validate_state(self.world_dir, state.model_copy(
                        update={"people": {**state.people, **reply.new_people}}))
                    save_state(self.world_dir, new_state)
                return outcome, minor_moves, new_state
            except ValueError as error:
                self.trace.write("world_validation_failed", error=str(error), raw_reply=result,
                                 turn=self.turn, attempt=attempt + 1)
                if attempt:
                    raise SessionError(f"World validation failed after one retry: {error}") from None
                request = f"World validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")


def _key(name: str) -> str:
    return fold(name).replace("_", " ").strip()
