"""One part-of-day tick; sessions are owned by a day's async context."""

from contextlib import AsyncExitStack
from pathlib import Path
from typing import Self

from story_engine.agents.character import CharacterAgent
from story_engine.agents.world import WorldAgent
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import append_event, load_state, read_events, save_state
from story_engine.world.models import Clock, Event, WorldState


class TickSession:
    """Keep one session per character and one World session for this world/day."""

    def __init__(self, world_dir: Path, run_dir: Path, *, root: Path = Path('.')):
        self.world_dir, self.run_dir, self.root = world_dir, run_dir, root
        self.active = False

    async def __aenter__(self) -> Self:
        models, self.settings = load_configs(self.root / 'config/models.yaml')
        self.day = load_state(self.world_dir).clock.day
        self.trace = TraceWriter(self.run_dir)
        self.stack = AsyncExitStack()
        await self.stack.__aenter__()
        try:
            self.characters = {}
            for slug in load_state(self.world_dir).characters:
                self.characters[slug] = await self.stack.enter_async_context(CharacterAgent(
                    self.root, self.run_dir, self.world_dir, slug, models.character,
                    self.settings.turn_cap, self.trace))
            self.world = await self.stack.enter_async_context(WorldAgent(
                self.root, self.run_dir, self.world_dir, models.world,
                self.settings.turn_cap, self.trace))
        except BaseException:
            await self.stack.aclose()
            raise
        self.active = True
        return self

    async def __aexit__(self, *args):
        self.active = False
        return await self.stack.__aexit__(*args)


async def run_tick(world_dir: Path, run_dir: Path, *, session: TickSession) -> WorldState:
    """Resolve one tick using the world's open day session; no scene or memory work."""
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
    events, updated, notes = await session.world.resolve(
        state, {slug: action.model_dump() for slug, action in choices.items()}, read_events(world_dir))
    for event in events:
        append_event(world_dir, event)
    parts = session.settings.parts_of_day
    index = parts.index(state.clock.part) + 1
    updated.clock = Clock(day=state.clock.day + (index == len(parts)),
                          part=parts[index % len(parts)])
    save_state(world_dir, updated)
    session.trace.write('situation_notes', day=state.clock.day, part=state.clock.part,
                        situation_notes=notes)
    return updated
