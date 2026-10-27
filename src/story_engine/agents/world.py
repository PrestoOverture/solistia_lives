"""The world's persistent resolving session for one day."""

import json
from pathlib import Path
from typing import Annotated, Literal, Self, Union

from claude_agent_sdk import ClaudeSDKClient, ResultMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from story_engine.agents.sdk import (
    run_call, KBHooks, SessionCost, SessionError, ThinkingUsage, json_schema_output, session_error,
    session_options, structured_reply,
)
from story_engine.config import Role, load_settings
from story_engine.agents.subjects import fold
from story_engine.trace import TraceWriter
from story_engine.world.io import commit_event, load_state, read_events, validate_state
from story_engine.world.ops import Op, Open
from story_engine.world.permissions import Authority, validate_ops
from story_engine.world.models import Clock, Event, Person, Place, Situation, WorldState


class OffscreenEvent(BaseModel):
    """Code fills actor, time, scene, and perception; ops carry every state change."""
    model_config = ConfigDict(extra="forbid")
    place: str
    content: str = Field(default='', max_length=280)
    spot: str | None = None
    ops: list[Op] = Field(default_factory=list)


class Encounter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mains: list[str] = Field(min_length=1)
    minor: list[str] = Field(default_factory=list)


class DayStartReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call: Literal["day_start"]
    ops: list[Op]

    @model_validator(mode="after")
    def valid_situations(self) -> Self:
        situations = [op.situation for op in self.ops if isinstance(op, Open)]
        if not 1 <= len(situations) <= 3:
            raise ValueError('day_start needs 1-3 open ops')
        if len(situations) >= 2:
            if len({s.kind for s in situations}) <= 1:
                raise ValueError("new situations must have more than one kind")
            if len({s.due.part for s in situations}) <= 1:
                raise ValueError("new situations must not have all the same due part")
        return self


class AdjudicateReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call: Literal["adjudicate"]
    encounters: list[Encounter] = Field(default_factory=list)
    ops: list[Op] = Field(default_factory=list)


class OffscreenReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    call: Literal["offscreen"]
    events: list[OffscreenEvent] = Field(default_factory=list)
    situation_notes: dict[str, str] = Field(default_factory=dict)


class MinorMove(BaseModel):
    """A minor participant's move: the same shape as a character's Action, minus intent."""

    model_config = ConfigDict(extra="forbid")
    move: Literal["act", "wait", "leave"]
    urge: int = 0
    to: str | None = None
    action: str = Field(default="", max_length=180)
    say: str = Field(default="", max_length=400)
    ops: list[Op] = Field(default_factory=list)

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
    resolution: Literal['succeeded', 'failed', 'pending', 'none'] | None = None
    outcome: str | None = Field(default=None, max_length=280)
    ops: list[Op] = Field(default_factory=list)
    minor_moves: dict[str, MinorMove] = Field(default_factory=dict)

    @model_validator(mode='after')
    def outcome_needs_resolution(self):
        if self.outcome is not None and self.resolution is None:
            raise ValueError('an outcome must resolve a winning act')
        return self


WorldReply = Annotated[Union[DayStartReply, AdjudicateReply, RoundResolution],
                       Field(discriminator="call")]


class _WorldSession:
    prompt_file = "world.md"
    reply_type = WorldReply
    agent_name = "world"
    include_scene_context = True

    def __init__(self, root: Path, run_dir: Path, world_dir: Path,
                 role: Role, max_turns: int, trace: TraceWriter) -> None:
        self.root, self.run_dir, self.world_dir = root, run_dir, world_dir
        self.role, self.max_turns, self.trace = role, max_turns, trace
        self.client = None
        self.opened = False
        self.seen: set[int] = set()
        self.last_state: dict | None = None
        self.turn = 0
        self.cost = SessionCost()
        self.parts_of_day = tuple(load_settings(root / "config/settings.yaml").parts_of_day)

    def _state_payload(self, state: dict) -> dict:
        """Send a snapshot once, then entry-level changes from the last input."""
        if self.last_state is None:
            payload = {"state": state}
        else:
            changes = {}
            removed = {}
            for section, current in state.items():
                previous = self.last_state[section]
                if section == "clock":
                    if current != previous:
                        changes[section] = current
                    continue
                if isinstance(current, list):
                    key = "slug" if section == "places" else "id"
                    before = {entry[key]: entry for entry in previous}
                    after = {entry[key]: entry for entry in current}
                    changed = [entry for name, entry in after.items()
                               if name not in before or entry != before[name]]
                else:
                    before, after = previous, current
                    changed = {name: entry for name, entry in after.items()
                               if name not in before or entry != before[name]}
                if changed:
                    changes[section] = changed
                missing = [name for name in before if name not in after]
                if missing:
                    removed[section] = missing
            if removed:
                changes["removed"] = removed
            payload = {"state_changes": changes}
        self.last_state = state
        return payload

    async def __aenter__(self) -> Self:
        if self.opened:
            raise SessionError("WorldAgent context can only be opened once")
        self.opened = True
        sources = [self.root / "prompts" / self.prompt_file]
        if self.include_scene_context:
            sources.append(self.world_dir / "scene_context.md")
        prompt = "\n\n".join(path.read_text(encoding="utf-8") for path in sources)
        self.hooks = KBHooks(self.root, self.run_dir, agent=self.agent_name, turn=1)
        self.options = session_options(self.root, self.run_dir, self.role, prompt,
                                       self.max_turns, self.hooks,
                                       output_format=json_schema_output(self.reply_type))
        self.context = ClaudeSDKClient(options=self.options)
        self.client = await self.context.__aenter__()
        return self

    async def __aexit__(self, *args):
        try:
            return await self.context.__aexit__(*args)
        finally:
            self.client = None

    async def _send(self, request: str):
        """Send one query and return (result_text, trace_fields) for the final reply."""
        thinking = ThinkingUsage()
        async def receive_call():
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
        return await run_call(
            receive_call(), role=self.role, trace=self.trace,
            stage=self.agent_name, agent=self.agent_name,
        )

    def _event_state(self, state: WorldState, event: Event, authority: Authority,
                     attempt: int, dropped: list[tuple[Event, str]]) -> WorldState | None:
        """Retry op rejections, then discard the whole atomic event group."""
        try:
            return validate_ops(state, event, authority)
        except ValueError as error:
            if attempt < self.role.retries:
                raise
            dropped.append((event, str(error)))
            return None

    def _trace_drops(self, call: str, dropped: list[tuple[Event, str]]) -> None:
        # Only report drops after the reply's remaining, non-op checks pass.
        for event, error in dropped:
            self.trace.write('event_dropped', call=call, turn=self.turn,
                             error=error, event=event.model_dump())


class WorldAgent(_WorldSession):
    async def day_start(self, state: WorldState, events: list[Event]) -> WorldState:
        """Add the day's situations from revised goals and yesterday's visible facts."""
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        request = json.dumps({
            "call": "day_start", "reply": "JSON with call: 'day_start' with ops, including 1-3 open ops",
            **self._state_payload(state.model_dump()),
            "events": [event.model_dump(exclude={"intent"}) for event in events
                       if event.day == state.clock.day - 1 and event.type != "plan" and not event.op_only],
        }, ensure_ascii=False)
        for attempt in range(self.role.retries + 1):
            result, structured_output, usage_fields = await self._send(request)
            if usage_fields is not None:
                self.trace.write("stage_usage", stage="world", agent="world", turn=self.turn,
                                 attempt=attempt + 1, **usage_fields)
            try:
                reply = DayStartReply.model_validate(structured_reply(result, structured_output))
                event = Event(id=0, **state.clock.model_dump(), place=state.places[0].slug, actor='world',
                              type='state_change', content='', perceived_by=[], ops=reply.ops)
                dropped = []
                updated = self._event_state(state, event, Authority('day_start'), attempt, dropped)
                if updated is not None:
                    commit_event(self.world_dir, event, authority=Authority('day_start'))
                self._trace_drops('day_start', dropped)
                return load_state(self.world_dir)
            except ValueError as error:
                self.trace.write("world_validation_failed", error=str(error), raw_reply=result,
                                 turn=self.turn, attempt=attempt + 1)
                if attempt == self.role.retries:
                    raise SessionError(f"World validation failed after {'one retry' if self.role.retries == 1 else str(self.role.retries) + ' retries'}: {error}") from None
                request = f"World validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")

    def _new_events(self, state: WorldState, events: list[Event]) -> list[Event]:
        new_events = [event for event in events
                      if event.day == state.clock.day and event.id not in self.seen and not event.op_only]
        self.seen.update(event.id for event in new_events)
        return new_events

    async def adjudicate(self, state: WorldState, choices: dict, events: list[Event]):
        """Encounter call: identify people at mains' current spots, introduce people/places."""
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        new_events = self._new_events(state, events)
        self.trace.write("call_input", agent=self.agent_name, call="adjudicate", turn=self.turn,
                         **state.clock.model_dump(), state=state.model_dump(), choices=choices,
                         max_event_id=max((event.id for event in events), default=0))
        request = json.dumps({**self._state_payload(state.model_dump()), "choices": choices,
                              "call": "adjudicate", "reply": "JSON with call: 'adjudicate', encounters and ops",
                              "events": [event.model_dump() for event in new_events]}, ensure_ascii=False)
        for attempt in range(self.role.retries + 1):
            result, structured_output, usage_fields = await self._send(request)
            if usage_fields is not None:
                self.trace.write("stage_usage", stage="world", agent="world", turn=self.turn,
                                 attempt=attempt + 1, **usage_fields)
            try:
                reply = AdjudicateReply.model_validate(structured_reply(result, structured_output))
                event = Event(id=0, **state.clock.model_dump(), place=state.places[0].slug,
                              actor='world', type='state_change', content='', perceived_by=[], ops=reply.ops)
                dropped = []
                updated = self._event_state(state, event, Authority('encounter'), attempt, dropped)
                if updated is None:
                    event, updated = None, state
                keys = {_key(name): name for name in updated.people}
                encounters = []
                name_drops = []

                def reject_name(name, main, error):
                    if attempt < self.role.retries:
                        raise ValueError(error)
                    name_drops.append(dict(name=name, main=main, error=error))

                for encounter in reply.encounters:
                    # The first valid main anchors this listing; scenes still group mains by state.
                    main = next((slug for slug in encounter.mains if slug in state.characters), None)
                    mains = []
                    spot = ((state.characters[main].where, state.characters[main].spot)
                            if main is not None else None)
                    for slug in encounter.mains:
                        character = state.characters.get(slug)
                        if character is None:
                            reject_name(slug, main, 'encounter mains must name main characters')
                        elif (character.where, character.spot) != spot:
                            reject_name(slug, main, 'encounter mains must share one place and spot')
                        else:
                            mains.append(slug)
                    if not mains:
                        continue
                    minors = []
                    for name in encounter.minor:
                        name = keys.get(_key(name), name)
                        person = updated.people.get(name)
                        if person is None or (person.where, person.spot) != spot:
                            reject_name(name, main, 'encounter minor must name a person at the same place and spot')
                        elif name not in minors:
                            minors.append(name)
                    encounters.append(Encounter(mains=mains, minor=minors))
                self._trace_drops('adjudicate', dropped)
                for fields in name_drops:
                    self.trace.write('encounter_name_dropped', call='adjudicate', turn=self.turn, **fields)
                return event, encounters, updated
            except ValueError as error:
                self.trace.write("world_validation_failed", error=str(error), raw_reply=result,
                                 turn=self.turn, attempt=attempt + 1)
                if attempt == self.role.retries:
                    raise SessionError(f"World validation failed after {'one retry' if self.role.retries == 1 else str(self.role.retries) + ' retries'}: {error}") from None
                request = f"World validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")

    async def round(self, state: WorldState, events: list[Event],
                    *, place: str, main_present: list[str], minor_present: list[str],
                    last_winner: dict | None, scene: str, round_number: int,
                    closing: bool = False):
        """Resolve the previous winning act and bid for minor participants' next moves."""
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        new_events = self._new_events(state, events)
        request = json.dumps({**self._state_payload(state.model_dump()), "call": "scene_round",
                              "reply": "JSON with call: 'scene_round'",
                              "place": place, "participants": {"main": main_present, "minor": minor_present},
                              "people": {name: state.people[name].model_dump() for name in minor_present
                                         if name in state.people},
                              "last_winner": last_winner, "closing": closing,
                              "events": [event.model_dump() for event in new_events]}, ensure_ascii=False)
        for attempt in range(self.role.retries + 1):
            result, structured_output, usage_fields = await self._send(request)
            if usage_fields is not None:
                self.trace.write("stage_usage", stage="world", agent="world", turn=self.turn,
                                 attempt=attempt + 1, **usage_fields)
            try:
                reply = RoundResolution.model_validate(structured_reply(result, structured_output))
                target = last_winner['id'] if last_winner else None
                if target is None and reply.resolution is not None:
                    raise ValueError('a resolution needs a winning act')
                if target is not None and reply.resolution is None:
                    raise ValueError('the winning act needs a resolution')
                if closing and reply.resolution == 'pending':
                    raise ValueError('closing resolution must finish the winning act')
                event = Event(id=0, **state.clock.model_dump(), place=place, actor='world',
                              of=(last_winner['actor'] if last_winner and last_winner['actor'] in state.characters else None),
                              type='world' if reply.outcome else 'state_change', content=reply.outcome or '',
                              perceived_by=list(main_present), scene=scene,
                              round=(round_number if closing else max(1, round_number - 1)),
                              resolves=target, resolution=reply.resolution, ops=reply.ops)
                dropped = []
                updated = self._event_state(state, event, Authority('scene_round'), attempt, dropped)
                if updated is None:
                    event, updated = None, state
                keys = {_key(name): name for name in updated.people}
                minors = {}
                move_drops = []
                for name, move in ({} if closing else reply.minor_moves).items():
                    name = keys.get(_key(name), name)
                    person = updated.people.get(name)
                    reason = None
                    if person is None or person.where != place:
                        reason = 'minor_moves name must be a people entry at this place'
                    elif main_present and person.spot != updated.characters[main_present[0]].spot:
                        reason = 'minor_moves person must be at the same spot'
                    if reason is not None:
                        if attempt < self.role.retries:
                            raise ValueError(reason)
                        move_drops.append(dict(name=name, reason=reason))
                        continue
                    content = ' '.join(value for value in (move.action, move.say if move.move != 'wait' else '') if value)
                    if move.move == 'leave':
                        content = (content + f' {name} leaves.').strip()
                    move_event = Event(
                        id=0, **state.clock.model_dump(), place=place, actor=name,
                        type='speech' if move.move == 'act' and move.say else 'action',
                        content=content,
                        perceived_by=list(main_present), scene=scene, round=round_number, ops=move.ops)
                    if self._event_state(updated, move_event, Authority('person_scene', name), attempt, dropped) is None:
                        continue
                    minors[name] = move
                self._trace_drops('closing_resolution' if closing else 'scene_round', dropped)
                if closing and reply.minor_moves:
                    self.trace.write('closing_minor_moves_ignored', call='closing_resolution',
                                     turn=self.turn, names=list(reply.minor_moves))
                for fields in move_drops:
                    self.trace.write('minor_move_dropped', call='scene_round', turn=self.turn, **fields)
                return event, minors, updated
            except ValueError as error:
                self.trace.write("world_validation_failed", error=str(error), raw_reply=result,
                                 turn=self.turn, attempt=attempt + 1)
                if attempt == self.role.retries:
                    raise SessionError(f"World validation failed after {'one retry' if self.role.retries == 1 else str(self.role.retries) + ' retries'}: {error}") from None
                request = f"World validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")


class OffscreenAgent(_WorldSession):
    prompt_file = "world_offscreen.md"
    reply_type = OffscreenReply
    agent_name = "world_offscreen"
    include_scene_context = False

    def _build_offscreen_event(self, raw: "OffscreenEvent", state: WorldState, places: set[str]) -> Event:
        if raw.place not in places:
            raise ValueError('World event place must be in places')
        spot = raw.spot
        event = Event(id=0, **state.clock.model_dump(), place=raw.place, actor='world',
                      type='world' if raw.content else 'state_change', content=raw.content,
                      perceived_by=[], ops=raw.ops)
        perceived_by = [slug for slug, character in state.characters.items()
                        if character.where == event.place and (spot is None or character.spot == spot)]
        return event.model_copy(update={"perceived_by": perceived_by})

    async def offscreen(self, state: WorldState, open_situations: set[str],
                        *, max_event_id: int | None = None):
        """Advance off-screen life in a session with no main-character context."""
        if self.client is None:
            raise SessionError("WorldAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        projection = state.model_dump(exclude={
            "characters": True, "situations": {"__all__": {"touches"}},
        })
        if max_event_id is None:
            max_event_id = max((event.id for event in read_events(self.world_dir)), default=0)
        self.trace.write("call_input", agent=self.agent_name, call="offscreen", turn=self.turn,
                         **state.clock.model_dump(), state=projection,
                         max_event_id=max_event_id,
                         # Internal validation/perception context; never sent to the model.
                         validation_state=state.model_dump(), open_situations=sorted(open_situations))
        request = json.dumps({"call": "offscreen", "reply": "JSON with call: 'offscreen'",
                              **self._state_payload(projection)}, ensure_ascii=False)
        for attempt in range(self.role.retries + 1):
            result, structured_output, usage_fields = await self._send(request)
            if usage_fields is not None:
                self.trace.write("stage_usage", stage="world_offscreen", agent=self.agent_name, turn=self.turn,
                                 attempt=attempt + 1, **usage_fields)
            try:
                reply = OffscreenReply.model_validate(structured_reply(result, structured_output))
                new_state = state
                resolved = []
                dropped = []
                for raw in reply.events:
                    # Ops may add a place used by this event; validate all references in order.
                    event = Event(id=max_event_id + len(resolved) + 1, **state.clock.model_dump(), place=raw.place,
                                  actor='world', type='world' if raw.content else 'state_change',
                                  content=raw.content, perceived_by=[], ops=raw.ops)
                    updated = self._event_state(new_state, event, Authority('offscreen', parts_of_day=self.parts_of_day),
                                                attempt, dropped)
                    if updated is None:
                        continue
                    places = {place.slug for place in updated.places}
                    resolved.append(self._build_offscreen_event(raw, updated, places))
                    new_state = updated
                if open_situations - reply.situation_notes.keys():
                    raise ValueError("situation_notes must cover every situation open at tick start")
                if any(not note.strip() for note in reply.situation_notes.values()):
                    raise ValueError("situation_notes must be non-empty sentences")
                self.last_reply = reply
                self._trace_drops('offscreen', dropped)
                return resolved, new_state, reply.situation_notes
            except ValueError as error:
                self.trace.write("world_validation_failed", error=str(error), raw_reply=result,
                                 turn=self.turn, attempt=attempt + 1)
                if attempt == self.role.retries:
                    raise SessionError(f"World validation failed after {'one retry' if self.role.retries == 1 else str(self.role.retries) + ' retries'}: {error}") from None
                # State validation includes main-character data internally. Never echo
                # Pydantic's input values into this isolated session's retry feedback.
                feedback = (json.dumps(error.errors(include_input=False, include_context=False,
                                                    include_url=False))
                            if isinstance(error, ValidationError) else str(error))
                request = f"World validation failed: {feedback}\nReturn corrected JSON."
        raise AssertionError("unreachable")


def _key(name: str) -> str:
    return fold(name).replace("_", " ").strip()
