"""One part-of-day tick; sessions are owned by a day's async context."""

import json
import shutil

from contextlib import AsyncExitStack
from pathlib import Path
from typing import Self

from story_engine.agents.character import CharacterAgent
from story_engine.agents.subjects import fold
from story_engine.agents.world import OffscreenAgent, WorldAgent
from story_engine.config import load_configs
from story_engine.kb import normalize_slug
from story_engine.trace import TraceWriter
from story_engine.world.io import (
    append_event, append_scene, commit_event, load_state, read_events, read_scenes, write_memory,
)
from story_engine.world.models import Clock, Event, SceneRecord, WorldState
from story_engine.world.ops import ClockOp, Move
from story_engine.world.permissions import Authority


class CostCapReached(RuntimeError):
    """The run exceeded its configured simulation cost cap."""


class _SimulationTrace(TraceWriter):
    def __init__(self, run_dir, billed, record_cost):
        super().__init__(run_dir)
        self.billed = billed
        self.record_cost = record_cost

    def write(self, event_type, **fields):
        if event_type == "stage_usage":
            fields["billed"] = self.billed(fields)
        super().write(event_type, **fields)
        if event_type == "stage_usage" and fields["billed"]:
            self.record_cost(float(fields.get("call_cost_usd") or 0.0))


class TickSession:
    """Keep character, World, and isolated off-screen sessions for this world/day."""

    def __init__(self, world_dir: Path, run_dir: Path, *, root: Path = Path('.')):
        self.world_dir, self.run_dir, self.root = world_dir, run_dir, root
        self.active = False

    async def __aenter__(self) -> Self:
        from story_engine.world.io import require_genesis
        require_genesis(self.world_dir)
        meta_path = self.run_dir / 'meta.json'
        models_file = (json.loads(meta_path.read_text()).get('models_file', 'config/models.yaml')
                       if meta_path.exists() else 'config/models.yaml')
        models, self.settings = load_configs(self.root / models_file)
        billed_by_agent = {name: role.base_url is None
                           for name, role in models}
        billed_by_agent.update({slug: models.character.base_url is None
                                for slug in load_state(self.world_dir).characters})
        billed_by_agent["world_offscreen"] = models.world.base_url is None

        def billed(row):
            return row.get("billed", billed_by_agent.get(row.get("agent"), True))

        self.day = load_state(self.world_dir).clock.day
        self.spend_usd = 0.0
        trace_path = self.run_dir / "trace.jsonl"
        if trace_path.exists():
            self.spend_usd = sum(
                row.get("call_cost_usd", 0.0) or 0.0
                for line in trace_path.read_text().splitlines()
                if (row := json.loads(line))["type"] == "stage_usage" and billed(row))
        self.trace = _SimulationTrace(
            self.run_dir, lambda row: billed_by_agent.get(row.get("agent"), True),
            self._record_cost)
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
            self.offscreen = await self.stack.enter_async_context(OffscreenAgent(
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
    plans = {}
    for slug, agent in session.characters.items():
        plans[slug] = await agent.choose(state.clock.part, before)
    for slug, plan in plans.items():
        # A plan is an intention, not a fact (D26): it is logged where the character stood
        # at tick start, and only its maker perceives it.
        place = state.characters[slug].where
        append_event(world_dir, Event(
            id=0, **state.clock.model_dump(), place=place, actor=slug,
            type='plan', content=plan.aim, intent=plan.intent, perceived_by=[slug]))
    positions = {slug: ((plan.where, plan.spot) if plan.kind == 'go' else
                         (state.characters[slug].where, state.characters[slug].spot))
                 for slug, plan in plans.items()}
    for slug, plan in plans.items():
        if plan.kind == 'go':
            commit_event(world_dir, Event(
                id=0, **state.clock.model_dump(), place=plan.where, actor=slug,
                type='action', content=f'{slug} goes to {plan.where}.',
                perceived_by=[other for other, position in positions.items()
                              if position == (plan.where, plan.spot)],
                ops=[Move(who=slug, place=plan.where, spot=plan.spot)]),
                authority=Authority('code'))
    state = load_state(world_dir)
    encounter_event, encounters, _ = await session.world.adjudicate(
        state, {slug: plan.model_dump() for slug, plan in plans.items()}, read_events(world_dir))
    if encounter_event.ops:
        commit_event(world_dir, encounter_event, authority=Authority('encounter'))
    updated = load_state(world_dir)
    groups = {}
    for slug, character in updated.characters.items():
        groups.setdefault((character.where, character.spot), []).append(slug)
    minors_by_spot = {}
    for encounter in encounters:
        main = encounter.mains[0]
        key = (updated.characters[main].where, updated.characters[main].spot)
        # Names are data references to `people`: resolve them to their keys, without duplicates.
        keys = {_person_key(name): name for name in updated.people}
        listed = minors_by_spot.setdefault(key, [])
        for name in encounter.minor:
            name = keys.get(_person_key(name), name)
            if name not in listed:
                listed.append(name)
    for (place, spot), present in groups.items():
        present = [slug for slug in present
                  if (updated.characters[slug].where, updated.characters[slug].spot) == (place, spot)]
        minors = list(minors_by_spot.get((place, spot), []))
        # A staged plan opens a scene even alone (D26): the outcome of an uncertain
        # attempt is never settled off-screen.
        staged = any(plans[slug].kind == 'attempt' for slug in present)
        if len(present) >= 2 or (len(present) == 1 and (minors or staged)):
            updated = await run_scene(world_dir, session, updated, place, present, minors, spot=spot)
    open_situations = {s.id for s in updated.situations if s.status == 'open'}
    events, updated, notes = await session.offscreen.offscreen(updated, open_situations)
    for event in events:
        commit_event(world_dir, event, authority=Authority('offscreen', parts_of_day=tuple(session.settings.parts_of_day)))
    updated = load_state(world_dir)
    parts = session.settings.parts_of_day
    index = parts.index(state.clock.part) + 1
    commit_event(world_dir, Event(
        id=0, **state.clock.model_dump(), place=updated.places[0].slug, actor='world',
        type='state_change', content='', perceived_by=[],
        ops=[ClockOp(day=state.clock.day + (index == len(parts)), part=parts[index % len(parts)])]),
        authority=Authority('code'))
    updated = load_state(world_dir)
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


async def run_scene(world_dir, session, state, place, main_present, minor_present, *, spot=None):
    scene_id = str(len(read_scenes(world_dir)) + 1)
    main_present, minor_present = list(main_present), list(minor_present)
    solo_attempt = len(main_present) == 1 and not minor_present
    all_participants = list(main_present) + list(minor_present)
    last_act, notes = {}, session.scene_notes
    pending_to, quiet = None, 0
    unresolved = []
    first_event_id, last_event_id = None, None
    reason = 'part_over'

    def log(event, authority):
        nonlocal first_event_id, last_event_id, state
        saved = commit_event(world_dir, event, authority=authority)
        state = load_state(world_dir)
        first_event_id = first_event_id if first_event_id is not None else saved.id
        last_event_id = saved.id
        return saved

    async def resolve(round_number, before, closing=False):
        nonlocal state
        target = unresolved[0] if unresolved else None
        outcome, minors, _ = await session.world.round(
            state, before, place=place, main_present=main_present, minor_present=minor_present,
            last_winner=target, scene=scene_id, round_number=round_number, closing=closing)
        if outcome.ops or outcome.resolves is not None or outcome.content:
            log(outcome, Authority('scene_round'))
        finished = target is not None and outcome.resolution != 'pending'
        if finished:
            unresolved.pop(0)
        return minors, finished

    for round_number in range(1, session.settings.scene_cap + 1):
        before = read_events(world_dir)
        minor_moves, finished = await resolve(round_number, before)
        if solo_attempt and finished:
            reason = 'resolved'
            round_number -= 1
            break
        before = read_events(world_dir)
        main_moves = {}
        for slug in main_present:
            # Each main sees the same facts, including the previous act's resolution,
            # and none of the other participants' current choices.
            main_moves[slug] = await session.characters[slug].act(before, note=notes.pop(slug, None))
        for name, move in minor_moves.items():
            if move.move != 'leave' and name not in minor_present:
                minor_present.append(name)
                if name not in all_participants:
                    all_participants.append(name)
        addressee = resolve_addressee(pending_to, main_present, minor_present)
        moves = {**main_moves, **minor_moves}
        winner, floor = choose_floor(moves, addressee, last_act)
        session.trace.write('scene_round', round=round_number, place=place, scene=scene_id,
                            moves={key: move.model_dump() for key, move in moves.items()},
                            winner=winner, floor=floor)
        for key, move in moves.items():
            is_main = key in main_present
            if move.move == 'act' and key != winner:
                if is_main:
                    notes[key] = f"Your move didn't happen: {winner} took the floor."
                continue
            if move.move == 'wait' and (not is_main or not (move.action.strip() or move.ops)):
                continue
            content = ' '.join(value for value in (move.action, move.say if move.move != 'wait' else '') if value)
            if move.move == 'leave':
                content = (content + f' {key} leaves.').strip()
            saved = log(Event(
                id=0, **state.clock.model_dump(), place=place, actor=key,
                type='speech' if move.move == 'act' and move.say else 'action',
                content=content, intent=move.intent if is_main else None, perceived_by=list(main_present),
                scene=scene_id, round=round_number, ops=move.ops),
                Authority('character_scene' if is_main else 'person_scene', key))
            if key == winner:
                unresolved.append({'id': saved.id, 'actor': key, 'round': round_number, **move.model_dump()})
        if winner:
            last_act[winner] = round_number
            pending_to = moves[winner].to
        elif not any(move.move == 'leave' for move in moves.values()):
            pending_to = None
        main_present = [slug for slug in main_present if moves[slug].move != 'leave']
        minor_present = [name for name in minor_present
                         if (name not in moves or moves[name].move != 'leave')
                         and (state.people[name].where, state.people[name].spot) == (place, spot)]
        quiet = 0 if winner else quiet + 1
        total = len(main_present) + len(minor_present)
        if not main_present:
            reason = 'no_main'
            break
        if not solo_attempt and total <= 1:
            reason = 'one_left' if total else 'dispersed'
            break
        if quiet >= 2:
            reason = 'quiet'
            break
    # Resolve every outstanding winner, including the final floor holder at cap/leave.
    while unresolved:
        await resolve(round_number, read_events(world_dir), closing=True)
    session.trace.write('scene_ended', place=place, scene=scene_id, reason=reason, rounds=round_number)
    append_scene(world_dir, SceneRecord(
        id=scene_id, day=state.clock.day, part=state.clock.part, place=place, spot=spot,
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
    from story_engine.world.io import require_genesis
    require_genesis(world_dir)
    checkpoint = run_dir / "world_before"
    _copy_world(world_dir, checkpoint)
    try:
        async with TickSession(world_dir, run_dir) as session:
            state = load_state(world_dir)
            day_started = (state.clock.day >= 2
                           and state.clock.part == session.settings.parts_of_day[0])
            if day_started:
                for slug, agent in session.characters.items():
                    ops = await agent.day_start()
                    commit_event(world_dir, Event(
                        id=0, **state.clock.model_dump(), place=state.characters[slug].where, actor=slug,
                        type='state_change', content='', perceived_by=[], ops=ops),
                        authority=Authority('character_day_start', slug))
                    state = load_state(world_dir)
                state = await session.world.day_start(state, read_events(world_dir))
            while state.clock.day == session.day:
                # Day start and its first tick share the pre-day-start checkpoint.
                if not day_started:
                    _copy_world(world_dir, checkpoint)
                state = await run_tick(world_dir, run_dir, session=session)
                day_started = False
            memories = {slug: await agent.summarize(read_events(world_dir))
                        for slug, agent in session.characters.items()}
            for slug, memory in memories.items():
                write_memory(world_dir, slug, memory)
    except BaseException:
        _copy_world(world_dir, run_dir / "world_failed")
        _copy_world(checkpoint, world_dir)
        raise
    return state


def _person_key(name: str) -> str:
    from story_engine.agents.subjects import fold
    return fold(name).replace("_", " ").strip()
