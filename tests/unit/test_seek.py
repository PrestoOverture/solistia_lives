"""Seek plans resolve data references before encounters, without model calls."""
import asyncio
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from story_engine.agents.character import Action, Plan
from story_engine.config import load_configs
from story_engine.simulation import run_tick
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state, read_events, read_scenes
from story_engine.world.models import Person, Place
from test_character_action import setup_agent

ROOT = Path(__file__).resolve().parents[2]


def test_tick_adds_catalog_destination_before_move(tmp_path, monkeypatch):
    reply = dict(call='plan', kind='go', intent='Visit', aim='Visit', where='flamechurch')
    agent, _, requests, _, run = setup_agent(
        tmp_path, monkeypatch, iter([json.dumps(reply), json.dumps(reply)]))
    world = agent.world_dir
    state = load_state(world)
    state.places = [Place(slug='montwise', details=[])]
    state.situations = []
    for character in state.characters.values():
        character.where, character.spot, character.commitments = 'montwise', None, []
    state.characters['agnea'].spot = 'library_exterior'
    (world / 'genesis.json').write_text(state.model_dump_json())
    (world / 'state.json').write_text(state.model_dump_json())

    async def stay(*_):
        return go('montwise', 'library_exterior')

    async def adjudicate(current, *_):
        return None, [], current

    async def offscreen(current, *_):
        return [], current, {}

    async def exercise():
        async with agent:
            session = SimpleNamespace(active=True, world_dir=world, run_dir=run, day=1, root=ROOT,
                characters={'agnea': SimpleNamespace(choose=stay), 'throne': agent},
                settings=load_configs()[1], trace=TraceWriter(run),
                world=SimpleNamespace(adjudicate=adjudicate),
                offscreen=SimpleNamespace(offscreen=offscreen))
            return await run_tick(world, run, session=session)

    result = asyncio.run(exercise())
    assert {p.slug for p in result.places} == {'montwise', 'flamechurch'}
    assert result.characters['throne'].where == 'flamechurch'
    assert len(requests) == 1
    rows = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert not any(row['type'] == 'plan_where_cleared' for row in rows)
    travel = next(e for e in read_events(world) if e.actor == 'throne' and e.ops)
    assert [op.model_dump() for op in travel.ops] == [
        dict(op='place', slug='flamechurch', add_details=[]),
        dict(op='move', who='throne', place='flamechurch', spot=None)]
    assert result == load_state(world)
    assert result.model_dump() == json.loads((world / 'state.json').read_text())


def go(where='cropdale', spot='tavern', seek=None):
    return Plan(call='plan', kind='go', intent='Visit', aim='Visit',
                where=where, spot=spot, seek=seek)


@pytest.mark.parametrize('case', ['moving_main', 'cycle', 'travelling_main', 'person',
                                  'chain', 'attempt', 'current_place', 'cycle_chain', 'person_unreached'])
@pytest.mark.parametrize('reverse', [False, True])
def test_seek_tick(tmp_path, case, reverse):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    state.people['Host'] = Person(where='cropdale', spot='village_square', wants=['Visit'], commitments=[])
    plans = {'agnea': go(seek='throne'), 'throne': go(spot='village_square')}
    expected = ('cropdale', 'village_square')
    if case in {'cycle', 'cycle_chain'}:
        plans['throne'] = go('festival_grounds', 'dance_stage', seek='agnea')
        expected = ('cropdale', 'tavern')  # agnea sorts first
        if case == 'cycle_chain':
            state.characters['temenos'] = state.characters['agnea'].model_copy(deep=True)
            plans['temenos'] = go(seek='throne')
            info = json.loads((world / 'world.json').read_text())
            info['characters'].append('temenos')
            (world / 'world.json').write_text(json.dumps(info))
    elif case in {'travelling_main', 'person_unreached'}:
        if case == 'person_unreached':
            state.places.append(Place(slug='montwise', details=[]))
        plans['throne'] = go('montwise', 'library_exterior')
        expected = ('montwise', 'library_exterior')
        if case == 'person_unreached':
            expected = ('cropdale', 'tavern')
            state.people['Host'].where = 'montwise'
            state.people['Host'].spot = 'library_exterior'
            plans['agnea'] = go(seek='Host')
    elif case in {'person', 'chain'}:
        plans['throne'] = go(seek='Host')
        if case == 'person':
            plans['agnea'] = go(seek='Host')
    elif case == 'attempt':
        state.characters['throne'].spot = 'dance_stage'
        plans['throne'] = Plan(call='plan', kind='attempt', intent='Try', aim='Try')
        expected = ('festival_grounds', 'dance_stage')
    elif case == 'current_place':
        plans['throne'] = go('festival_grounds', 'dance_stage')
        expected = ('festival_grounds', 'dance_stage')
    (world / 'genesis.json').write_text(state.model_dump_json())

    class Character:
        def __init__(self, slug):
            self.slug = slug
        async def choose(self, *_):
            return plans[self.slug]
        async def act(self, *_, **kwargs):
            return Action(call='action', intent='Rest', move='wait', urge=0, action='', say='')

    async def adjudicate(current, *_):
        assert (current.characters['agnea'].where, current.characters['agnea'].spot) == expected
        return None, [], current

    async def round_(current, *_, **kwargs):
        return None, {}, current

    async def offscreen(current, *_):
        return [], current, {}

    order = list(reversed(plans)) if reverse else list(plans)
    session = SimpleNamespace(active=True, world_dir=world, run_dir=run, day=1, root=ROOT,
        characters={s: Character(s) for s in order}, scene_notes={}, settings=load_configs()[1],
        trace=TraceWriter(run), world=SimpleNamespace(adjudicate=adjudicate, round=round_),
        offscreen=SimpleNamespace(offscreen=offscreen))
    result = asyncio.run(run_tick(world, run, session=session))
    assert (result.characters['agnea'].where, result.characters['agnea'].spot) == expected
    if case == 'travelling_main':
        travel = next(e for e in read_events(world) if any(op.op == 'place' for op in e.ops))
        assert [op.op for op in travel.ops] == ['place', 'move']
        assert travel.ops[0].slug == 'montwise'
    scenes = read_scenes(world)
    if case != 'person_unreached':
        participants = set(plans) | ({'Host'} if case in {'moving_main', 'person', 'chain'} else set())
        assert len(scenes) == 1 and set(scenes[0].participants) == participants
        assert all((c.where, c.spot) == expected for c in result.characters.values())
    else:
        assert scenes == []
    move = next(e for e in read_events(world) if e.actor == 'agnea' and e.ops)
    assert move.content == f'agnea goes to find {plans["agnea"].seek}.'
    assert set(move.perceived_by) == ({'agnea'} if case == 'person_unreached' else set(plans))
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    unreached = [row for row in trace if row['type'] == 'seek_unreached']
    assert len(unreached) == (case == 'person_unreached')
    absent = [e for e in read_events(world) if e.type == 'world']
    if case == 'person_unreached':
        assert len(absent) == 1
        event = absent[0]
        assert event.content == f"{plans['agnea'].seek} isn't here."
        assert event.perceived_by == ['agnea']
        assert event.place == expected[0] and event.ops == []
    else:
        assert absent == []
    assert result == load_state(world)
    assert result.model_dump() == json.loads((world / 'state.json').read_text())


@pytest.mark.parametrize('target', ['missing', 'throne', 'Agnea', ''])
@pytest.mark.parametrize('corrected', [False, True])
def test_invalid_seek_retries_then_clears(tmp_path, monkeypatch, target, corrected):
    bad = dict(call='plan', kind='go', intent='Visit', aim='Visit', where='cropdale', seek=target)
    good = {**bad, 'seek': 'agnea'}
    agent, clients, requests, _, run = setup_agent(
        tmp_path, monkeypatch, iter(map(json.dumps, [bad, good if corrected else bad])))

    async def exercise():
        async with agent:
            return await agent.choose('morning', [])

    result = asyncio.run(exercise())
    assert result.seek == ('agnea' if corrected else None)
    assert len(requests) == 2 and 'seek must name another main character' in requests[1]
    rows = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert len([r for r in rows if r['type'] == 'plan_seek_cleared']) == (not corrected)


def test_seek_enum_refreshes_per_call_and_prompt_is_stable(tmp_path, monkeypatch):
    replies = [dict(call='plan', kind='go', intent='Visit', aim='Visit', where='cropdale'),
               dict(call='plan', kind='go', intent='Visit', aim='Visit', where='cropdale', seek='Host')]
    agent, clients, requests, _, _ = setup_agent(tmp_path, monkeypatch, iter(map(json.dumps, replies)))

    async def exercise():
        async with agent:
            assert (await agent.choose('morning', [])).seek is None
            prompt = clients[0].options.system_prompt
            state = load_state(agent.world_dir)
            state.people['Host'] = Person(where='cropdale', spot='tavern', wants=['Visit'], commitments=[])
            (agent.world_dir / 'genesis.json').write_text(state.model_dump_json())
            assert (await agent.choose('morning', [])).seek == 'Host'
            assert clients[1].options.system_prompt == prompt
            assert 'Host' not in prompt

    asyncio.run(exercise())
    assert json.loads(requests[0])['seek_schema'] == {'enum': ['agnea', None], 'default': None}
    assert json.loads(requests[1])['seek_schema'] == {'enum': ['Host', 'agnea', None], 'default': None}


@pytest.mark.parametrize('kind', ['go', 'attempt'])
@pytest.mark.parametrize('corrected', [False, True])
def test_invalid_where_retries_then_clears(tmp_path, monkeypatch, kind, corrected):
    bad = dict(call='plan', kind=kind, intent='Visit', aim='Visit',
               where='missing', spot='tavern')
    good = {**bad, 'where': 'cropdale'}
    agent, _, requests, _, run = setup_agent(
        tmp_path, monkeypatch, iter(map(json.dumps, [bad, good if corrected else bad])))

    async def exercise():
        async with agent:
            return await agent.choose('morning', [])

    result = asyncio.run(exercise())
    assert result.where == ('cropdale' if corrected else None)
    assert result.spot == ('tavern' if corrected else None)
    assert len(requests) == 2 and 'where must name a place in state or a stage catalog' in requests[1]
    rows = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    cleared = [row for row in rows if row['type'] == 'plan_where_cleared']
    assert len(cleared) == (not corrected)
    if not corrected:
        assert {key: cleared[0][key] for key in ('agent', 'turn', 'error', 'where')} == {
            'agent': 'throne', 'turn': 1,
            'error': 'where must name a place in state or a stage catalog', 'where': 'missing'}
