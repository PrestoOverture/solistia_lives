"""One part-of-day tick; sessions are owned by a day's async context."""

import json
import shutil

from contextlib import AsyncExitStack
from pathlib import Path
from typing import Self

from story_engine.agents.character import CharacterAgent
from story_engine.agents.subjects import fold
from story_engine.agents.world import WorldAgent
from story_engine.config import load_configs
from story_engine.kb import normalize_slug
from story_engine.trace import TraceWriter
from story_engine.world.io import (
    append_event, append_scene, load_state, read_events, read_scenes, save_state, write_memory,
)
from story_engine.world.models import Clock, Event, SceneRecord, WorldState


class CostCapReached(RuntimeError):
    """The run exceeded its configured simulation cost cap."""


class TickSession:
    """Keep one session per character and one World session for this world/day."""

    def __init__(self, world_dir: Path, run_dir: Path, *, root: Path = Path('.')):
        self.world_dir, self.run_dir, self.root = world_dir, run_dir, root
        self.active = False

    async def __aenter__(self) -> Self:
        models, self.settings = load_configs(self.root / 'config/models.yaml')
        self.day = load_state(self.world_dir).clock.day
        self.spend_usd = 0.0
        trace_path = self.run_dir / "trace.jsonl"
        if trace_path.exists():
            self.spend_usd = sum(
                row.get("call_cost_usd", 0.0) or 0.0
                for line in trace_path.read_text().splitlines()
                if (row := json.loads(line))["type"] == "stage_usage")
        self.trace = TraceWriter(self.run_dir, on_usage=self._record_cost)
        self._record_cost(0.0)
        self.stack = AsyncExitStack()
        await self.stack.__aenter__()
        try:
            self.scene_notes = {}
            self.characters = {}
            for slug in load_state(self.world_dir).characters:
                self.characters[slug] = await self.stack.enter_async_context(CharacterAgent(
                    self.root, self.run_dir, self.world_dir, slug, models.character,
                    self.settings.agent_max_turns, self.trace))
            self.world = await self.stack.enter_async_context(WorldAgent(
                self.root, self.run_dir, self.world_dir, models.world,
                self.settings.agent_max_turns, self.trace))
        except BaseException:
            await self.stack.aclose()
            raise
        self.active = True
        return self

    def _record_cost(self, cost: float) -> None:
        self.spend_usd += cost
        if self.spend_usd > self.settings.max_cost_usd:
            self.trace.write("cost_cap_reached", spend_usd=self.spend_usd,
                             max_cost_usd=self.settings.max_cost_usd)
            raise CostCapReached(f"Run spend ${self.spend_usd:.6f} exceeds "
                                 f"${self.settings.max_cost_usd:.6f}")

    async def __aexit__(self, *args):
        self.active = False
        return await self.stack.__aexit__(*args)


async def run_tick(world_dir: Path, run_dir: Path, *, session: TickSession) -> WorldState:
    """Resolve one tick using the world's open day session; including scenes before advancing the clock."""
    if not session.active or (session.world_dir, session.run_dir) != (world_dir, run_dir):
        raise ValueError('run_tick requires an open session for this world and run')
    state = load_state(world_dir)
    if state.clock.day != session.day:
        raise ValueError('Open a new TickSession for the next day')
    before = read_events(world_dir)
    choices = {}
    for slug, agent in session.characters.items():
        choices[slug] = await agent.choose(state.clock.part, before)
    for slug, action in choices.items():
        place = state.characters[slug].where
        append_event(world_dir, Event(
            id=0, **state.clock.model_dump(), place=place, actor=slug,
            type='speech' if action.say else 'action',
            content=' '.join(value for value in (action.action, action.say) if value),
            intent=action.intent,
            perceived_by=[name for name, character in state.characters.items()
                          if character.where == place]))
    events, updated, notes, encounters = await session.world.resolve(
        state, {slug: action.model_dump() for slug, action in choices.items()}, read_events(world_dir))
    for event in events:
        append_event(world_dir, event)
    groups = {}
    for slug, character in updated.characters.items():
        groups.setdefault(character.where, []).append(slug)
    minors_by_place = {encounter.place: encounter.minor for encounter in encounters}
    for place, present in groups.items():
        present = [slug for slug in present if updated.characters[slug].where == place]
        minors = list(minors_by_place.get(place, []))
        if len(present) >= 2 or (len(present) == 1 and minors):
            updated = await run_scene(world_dir, session, updated, place, present, minors)
    parts = session.settings.parts_of_day
    index = parts.index(state.clock.part) + 1
    updated.clock = Clock(day=state.clock.day + (index == len(parts)),
                          part=parts[index % len(parts)])
    save_state(world_dir, updated)
    session.trace.write('situation_notes', day=state.clock.day, part=state.clock.part,
                        situation_notes=notes)
    return updated


def choose_floor(moves, addressee, last_act):
    """Select an act without consulting an agent; stable order breaks equal recency."""
    acts = [key for key, move in moves.items() if move.move == 'act']
    if not acts:
        return None, 'nobody'
    if addressee in acts:
        cutters = [key for key in acts if key != addressee
                   and moves[key].urge == 3 and moves[addressee].urge < 3]
        if not cutters:
            return addressee, 'addressee'
        acts, reason = cutters, 'interrupt'
    else:
        reason = 'only bid' if len(acts) == 1 else 'urge'
    top = max(moves[key].urge for key in acts)
    tied = [key for key in acts if moves[key].urge == top]
    if len(tied) > 1 and reason == 'urge':
        reason = 'tie-break'
    return min(tied, key=lambda key: last_act.get(key, -1)), reason


def resolve_addressee(to, main_present, minor_present):
    """Match a spoken-to name against present main characters (by slug/alias) or minors (by name)."""
    if not to:
        return None
    slug = normalize_slug(to)
    if slug in main_present:
        return slug
    for name in minor_present:
        if fold(name) == fold(to):
            return name
    return None


async def run_scene(world_dir, session, state, place, main_present, minor_present):
    scene_id = str(len(read_scenes(world_dir)) + 1)
    main_present, minor_present = list(main_present), list(minor_present)
    all_participants = list(main_present) + [name for name in minor_present if name not in main_present]
    last_act, notes = {}, session.scene_notes
    pending_to, quiet, last_winner = None, 0, None
    first_event_id, last_event_id = None, None
    reason = 'part_over'

    def log(event):
        nonlocal first_event_id, last_event_id
        saved = append_event(world_dir, event.model_copy(update={'scene': scene_id}))
        first_event_id = first_event_id if first_event_id is not None else saved.id
        last_event_id = saved.id
        return saved

    for round_number in range(1, session.settings.scene_cap + 1):
        before = read_events(world_dir)
        main_moves = {}
        for slug in main_present:
            main_moves[slug] = await session.characters[slug].act(before, note=notes.pop(slug, None))
        outcome, minor_moves = await session.world.round(
            state, before, place=place, main_present=main_present, minor_present=minor_present,
            last_winner=last_winner)
        if outcome:
            log(outcome)
        # A minor joins only when the World brings them in with a move here; an
        # unresolved `to` from the previous round's winner never creates one.
        for name, move in minor_moves.items():
            if move.move != 'leave' and name not in minor_present:
                minor_present.append(name)
                all_participants.append(name)
        # Re-resolve who was addressed against the now-current participants: the
        # World may have just brought in the very name that was spoken to.
        addressee = resolve_addressee(pending_to, main_present, minor_present)
        moves = {**main_moves, **minor_moves}
        winner, floor = choose_floor(moves, addressee, last_act)
        session.trace.write('scene_round', round=round_number, place=place, scene=scene_id,
                            moves={key: move.model_dump() for key, move in moves.items()},
                            winner=winner, floor=floor)
        happened = {}
        for key, move in moves.items():
            is_main = key in main_present
            if move.move == 'act' and key != winner:
                if is_main:
                    notes[key] = f"Your move didn't happen: {winner} took the floor."
                continue
            if move.move == 'wait' and not move.action.strip():
                continue
            happened[key] = move.model_dump()
            content = ' '.join(value for value in (move.action, move.say if move.move != 'wait' else '') if value)
            if move.move == 'leave':
                content = (content + f' {key} leaves.').strip()
            log(Event(
                id=0, **state.clock.model_dump(), place=place, actor=key,
                type='speech' if move.move == 'act' and move.say else 'action',
                content=content, intent=move.intent if is_main else None, perceived_by=list(main_present)))
        if winner:
            last_act[winner] = round_number
            pending_to = moves[winner].to
            last_winner = {'actor': winner, **moves[winner].model_dump()}
        else:
            last_winner = None
            if not any(move.move == 'leave' for move in moves.values()):
                pending_to = None
        main_present = [slug for slug in main_present if moves[slug].move != 'leave'
                        and state.characters[slug].where == place]
        minor_present = [name for name in minor_present
                         if name not in moves or moves[name].move != 'leave']
        quiet = 0 if winner else quiet + 1
        total = len(main_present) + len(minor_present)
        if not main_present:
            reason = 'no_main'
            break
        if total <= 1:
            reason = 'one_left' if total else 'dispersed'
            break
        if quiet >= 2:
            reason = 'quiet'
            break
    session.trace.write('scene_ended', place=place, scene=scene_id, reason=reason, rounds=round_number)
    append_scene(world_dir, SceneRecord(
        id=scene_id, day=state.clock.day, part=state.clock.part, place=place,
        participants=all_participants, first_event_id=first_event_id or 0,
        last_event_id=last_event_id or 0, rounds=round_number, end=reason))
    return state


def _copy_world(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("state.json", "events.jsonl", "scenes.jsonl", "memory"):
        target = destination / name
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink(missing_ok=True)
        origin = source / name
        if origin.is_dir():
            shutil.copytree(origin, target)
        elif origin.exists():
            shutil.copy2(origin, target)


async def run_day(world_dir: Path, run_dir: Path) -> WorldState:
    """Commit completed parts; roll back the failing part after preserving evidence."""
    checkpoint = run_dir / "world_before"
    _copy_world(world_dir, checkpoint)
    try:
        async with TickSession(world_dir, run_dir) as session:
            state = load_state(world_dir)
            while state.clock.day == session.day:
                _copy_world(world_dir, checkpoint)
                state = await run_tick(world_dir, run_dir, session=session)
            memories = {slug: await agent.summarize(read_events(world_dir))
                        for slug, agent in session.characters.items()}
            for slug, memory in memories.items():
                write_memory(world_dir, slug, memory)
            save_state(world_dir, state)
    except BaseException:
        _copy_world(world_dir, run_dir / "world_failed")
        _copy_world(checkpoint, world_dir)
        raise
    return state
