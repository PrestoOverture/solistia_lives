"""Every floor winner has a final resolution, including at scene termination."""
import asyncio
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from story_engine.agents.character import Action
from story_engine.simulation import run_scene
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state, read_events, read_scenes
from story_engine.world.models import Event

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('end', ['cap', 'leave', 'quiet', 'pending', 'solo'])
def test_every_winner_resolved_and_solo_finishes(tmp_path, end):
    world = tmp_path / 'world'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    state = load_state(world)
    class Character:
        def __init__(self, slug): self.slug, self.turn = slug, 0
        async def act(self, before, note=None):
            self.turn += 1
            move = ('leave' if self.turn > 1 and end == 'leave' else
                    'wait' if self.turn > 1 and end == 'quiet' else 'act')
            return Action(call='action', intent='Try', move=move, urge=2 if move == 'act' else 0,
                          action=f'{self.slug} tries.' if move == 'act' else '', say='')
    calls = []
    async def resolve(current, events, **kwargs):
        calls.append(kwargs)
        target = kwargs['last_winner']
        resolution = 'none' if target else None
        if target and end == 'pending' and sum(c['last_winner'] is not None for c in calls) == 1:
            resolution = 'pending'
        event = Event(id=0, **current.clock.model_dump(), place=kwargs['place'], actor='world',
                      of=target['actor'] if target else None, type='state_change', content='', perceived_by=[],
                      scene=kwargs['scene'], round=kwargs['round_number'] if kwargs['closing'] else max(1, kwargs['round_number'] - 1),
                      resolves=target['id'] if target else None, resolution=resolution)
        return event, {}, current
    mains = ['agnea'] if end == 'solo' else ['agnea', 'throne']
    characters = {slug: Character(slug) for slug in mains}
    session = SimpleNamespace(world=SimpleNamespace(round=resolve), characters=characters,
                              scene_notes={}, settings=SimpleNamespace(scene_cap=4), trace=TraceWriter(tmp_path))
    result = asyncio.run(run_scene(world, session, state, 'festival_grounds', mains, []))
    events = read_events(world)
    acts = [e for e in events if e.type in {'action', 'speech'} and e.content.endswith('tries.')]
    finals = [e for e in events if e.resolves is not None and e.resolution != 'pending']
    assert {e.id for e in acts} == {e.resolves for e in finals}
    assert len(finals) == len(acts)
    assert all(e.scene == '1' for e in finals)
    if end == 'solo':
        assert read_scenes(world)[0].end == 'resolved'
        assert characters['agnea'].turn == 1 and len(acts) == 1
    if end in {'cap', 'pending'}:
        assert calls[-1]['closing'] is True
    if end == 'pending':
        assert any(e.resolution == 'pending' for e in events)
    assert result == load_state(world)


def test_go_is_code_movement_and_every_attempt_is_a_scene(tmp_path):
    from story_engine.agents.character import Plan
    from story_engine.simulation import run_tick
    from story_engine.config import load_configs
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    class Character:
        def __init__(self, slug): self.slug = slug
        async def choose(self, part, before):
            return Plan(call='plan', kind='attempt', intent='Search', aim='Search this spot') if self.slug == 'agnea' else Plan(
                call='plan', kind='go', intent='Travel', aim='Go to town', where='cropdale', spot='gate')
        async def act(self, before, note=None):
            return Action(call='action', intent='Search', move='act', urge=2, action='Agnea searches.', say='')
    async def encounters(state, choices, events):
        assert state.characters['throne'].where == 'cropdale'
        assert state.characters['agnea'].where == 'festival_grounds'
        return Event(id=0, **state.clock.model_dump(), place='cropdale', actor='world',
                     type='state_change', content='', perceived_by=[]), [], state
    async def round_(state, events, **kwargs):
        target = kwargs['last_winner']
        return Event(id=0, **state.clock.model_dump(), place=kwargs['place'], actor='world',
                     of=target['actor'] if target else None, scene=kwargs['scene'],
                     round=max(1, kwargs['round_number']-1), type='state_change', content='', perceived_by=[],
                     resolves=target['id'] if target else None, resolution='none' if target else None), {}, state
    async def offscreen(state, open_situations):
        return [], state, {}
    session = SimpleNamespace(active=True, world_dir=world, run_dir=run, day=1,
                              characters={s: Character(s) for s in ['agnea', 'throne']}, scene_notes={},
                              settings=load_configs()[1], trace=TraceWriter(run),
                              world=SimpleNamespace(adjudicate=encounters, round=round_),
                              offscreen=SimpleNamespace(offscreen=offscreen))
    result = asyncio.run(run_tick(world, run, session=session))
    scenes = read_scenes(world)
    assert len(scenes) == 1 and scenes[0].participants == ['agnea'] and scenes[0].end == 'resolved'
    assert not any(e.of is not None and e.scene is None for e in read_events(world))
    assert result == type(result).model_validate_json((world / 'state.json').read_text())
