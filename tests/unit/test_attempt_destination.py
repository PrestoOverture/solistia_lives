"""Attempts travel before their encounter and scene, without model calls."""
import asyncio
from types import SimpleNamespace

import pytest

from story_engine.agents.character import Action, Plan
from story_engine.config import load_configs
from story_engine.simulation import run_tick
from story_engine.trace import TraceWriter
from story_engine.world.io import create_world, load_state, read_events, read_scenes
from story_engine.world.models import CharacterState, Clock, Person, Place, WorldState


@pytest.mark.parametrize('destination', ['spot', 'person', 'stay'])
def test_attempt_destination(tmp_path, destination):
    state = WorldState(clock=Clock(day=1, part='morning'),
        places=[Place(slug='montwise', details=[])],
        characters={'osvald': CharacterState(where='montwise', spot='the_well',
                                           goals=['Study'], commitments=[])},
        people={'Librarian': Person(where='montwise', spot='library_exterior',
                                    wants=['Study'], commitments=[])}, situations=[])
    world = create_world(['osvald'], 'montwise', 'Study', state, worlds_dir=tmp_path / 'worlds')
    run = tmp_path / 'run'
    run.mkdir()
    fields = ({'where': 'montwise', 'spot': 'library_exterior'} if destination == 'spot'
              else {'seek': 'Librarian'} if destination == 'person' else {})
    expected = 'the_well' if destination == 'stay' else 'library_exterior'

    class Character:
        async def choose(self, *_):
            return Plan(call='plan', kind='attempt', intent='Study', aim='Ask about books', **fields)
        async def act(self, *_, **kwargs):
            return Action(call='action', intent='Study', move='wait', urge=0, action='', say='')

    async def adjudicate(current, *_):
        assert current.characters['osvald'].spot == expected
        encounters = [SimpleNamespace(mains=['osvald'], minor=['Librarian'])] if destination == 'person' else []
        return None, encounters, current

    scene_spots = []
    async def round_(current, *_, **kwargs):
        scene_spots.append(current.characters['osvald'].spot)
        return None, {}, current

    async def offscreen(current, *_):
        return [], current, {}

    session = SimpleNamespace(active=True, world_dir=world, run_dir=run, day=1,
        characters={'osvald': Character()}, scene_notes={}, settings=load_configs()[1],
        trace=TraceWriter(run), world=SimpleNamespace(adjudicate=adjudicate, round=round_),
        offscreen=SimpleNamespace(offscreen=offscreen))
    result = asyncio.run(run_tick(world, run, session=session))
    assert result.characters['osvald'].spot == expected
    scenes = read_scenes(world)
    assert len(scenes) == 1 and scenes[0].spot == expected
    assert scenes[0].participants == (['osvald', 'Librarian'] if destination == 'person' else ['osvald'])
    assert scene_spots and set(scene_spots) == {expected}
    moves = [e for e in read_events(world) if e.actor == 'osvald' and e.ops]
    assert len(moves) == (destination != 'stay')
    if moves:
        assert moves[0].ops[0].op == 'move' and moves[0].ops[0].spot == expected
        assert moves[0].content == ('osvald goes to find Librarian.' if destination == 'person'
                                    else 'osvald goes to montwise.')
    assert result == load_state(world)


@pytest.mark.parametrize('fields,expected', [
    ({'where': 'cropdale', 'spot': 'tavern', 'seek': 'agnea'}, 'valid'),
    ({'where': 'missing'}, 'where'),
    ({'where': 'cropdale', 'spot': 'missing'}, 'spot'),
    ({'seek': 'missing'}, 'seek'),
])
def test_attempt_field_checks(tmp_path, monkeypatch, fields, expected):
    import json
    from test_character_action import setup_agent

    reply = json.dumps(dict(call='plan', kind='attempt', intent='Study', aim='Study', **fields))
    agent, _, requests, _, _ = setup_agent(tmp_path, monkeypatch, iter([reply, reply]))

    async def choose():
        async with agent:
            return await agent.choose('morning', [])

    result = asyncio.run(choose())
    if expected == 'valid':
        assert (result.where, result.spot, result.seek) == ('cropdale', 'tavern', 'agnea')
    else:
        assert getattr(result, expected) is None
    assert len(requests) == (1 if expected == 'valid' else 2)
