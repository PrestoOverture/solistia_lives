"""World op retries discard atomic events, using only mocked SDK responses."""
import asyncio
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from story_engine import simulation
from story_engine.agents import world as world_agent
from story_engine.agents.character import Action
from story_engine.agents.sdk import SessionError
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import commit_event, load_state, read_events, read_scenes
from story_engine.world.models import Person, WorldState
from story_engine.world.permissions import Authority
from test_day_start import fake_sdk, situation

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def workspace(tmp_path):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    state.people['Host'] = Person(where='festival_grounds', wants=['Help'], commitments=[])
    (world / 'genesis.json').write_text(state.model_dump_json())
    (world / 'state.json').write_text(state.model_dump_json())
    return world, run


def rows(run, kind):
    return [row for row in map(json.loads, (run / 'trace.jsonl').read_text().splitlines())
            if row['type'] == kind]


def assert_fold(world, state):
    assert load_state(world) == state == WorldState.model_validate_json((world / 'state.json').read_text())


def open_agent(workspace, cls=world_agent.WorldAgent):
    world, run = workspace
    models, settings = load_configs()
    return cls(ROOT, run, world, models.world, settings.agent_max_turns, TraceWriter(run))


@pytest.mark.parametrize('failure', ['op', 'schema', 'nonop'])
def test_mocked_day_continues_after_offscreen_op_drop(workspace, monkeypatch, failure):
    world, run = workspace
    initial = load_state(world)
    forbidden = dict(place='cropdale', content='A discarded event.', ops=[
        dict(op='place', slug='discarded', add_details=['Must roll back']),
        dict(op='situation', id=initial.situations[0].id, status='resolved')])
    valid = dict(place='cropdale', content='The stalls open.', ops=[
        dict(op='place', slug='cropdale', add_details=['Open stalls'])])
    bad = dict(forbidden, actor='agnea') if failure == 'schema' else forbidden

    def respond(client, request):
        if isinstance(request, str):
            request = next(r for r in reversed(client.calls) if isinstance(r, dict))
        call = request['call']
        if call == 'part_of_day':
            return dict(call='plan', kind='go', intent='Visit', aim='Walk to the stalls.',
                        where='cropdale' if clients.index(client) == 0 else 'festival_grounds', spot=None)
        if call == 'adjudicate':
            return dict(call=call)
        if call == 'end_of_day':
            return dict(call=call, summary='Visited the stalls.')
        assert call == 'offscreen'
        return dict(call=call, events=[bad, valid], situation_notes={} if failure == 'nonop' else
                    {s.id: 'Unchanged.' for s in load_state(world).situations})

    clients = fake_sdk(monkeypatch, respond)
    original = simulation.TickSession
    monkeypatch.setattr(simulation, 'TickSession', lambda w, r: original(w, r, root=ROOT))
    if failure != 'op':
        with pytest.raises(SessionError, match='Extra inputs' if failure == 'schema' else 'cover every situation'):
            asyncio.run(simulation.run_day(world, run))
        assert_fold(world, initial)
        assert read_events(world) == []
        assert rows(run, 'event_dropped') == []
        assert len(rows(run, 'world_validation_failed')) == 2
        return

    result = asyncio.run(simulation.run_day(world, run))
    assert result.clock.model_dump() == dict(day=2, part='morning')
    assert_fold(world, result)
    assert result.situations == initial.situations
    assert 'discarded' not in {p.slug for p in result.places}
    assert 'Open stalls' in next(p for p in result.places if p.slug == 'cropdale').details
    assert len([e for e in read_events(world) if e.content == valid['content']]) == 4
    assert not any(e.content == forbidden['content'] for e in read_events(world))
    drops = rows(run, 'event_dropped')
    assert len(drops) == 4
    for turn, drop in enumerate(drops, 1):
        assert drop['call'] == 'offscreen' and drop['turn'] == turn
        assert 'offscreen may not commit situation' in drop['error']
        assert drop['event']['content'] == forbidden['content']
        assert drop['event']['ops'] == forbidden['ops']
    feedback = [r for r in clients[3].calls if isinstance(r, str)]
    assert len(feedback) == 4 and all('may not commit situation' in r for r in feedback)
    assert all((world / 'memory' / f'{slug}.md').exists() for slug in initial.characters)


@pytest.mark.parametrize('failure', ['minor_spot', 'minor_place', 'minor_unknown', 'main_spot', 'schema'])
def test_mocked_day_encounter_name_retry_and_schema_failure(workspace, monkeypatch, failure):
    world, run = workspace
    initial = load_state(world)
    if failure == 'minor_place':
        initial.people['Host'].where = 'cropdale'
    else:
        initial.people['Host'].spot = 'elsewhere'
    if failure == 'main_spot':
        initial.characters['throne'].spot = 'elsewhere'
        initial.characters['hikari'] = initial.characters['agnea'].model_copy(deep=True)
        info_path = world / 'world.json'
        info = json.loads(info_path.read_text())
        info['characters'] = list(initial.characters)
        info_path.write_text(json.dumps(info))
    for path in ('genesis.json', 'state.json'):
        (world / path).write_text(initial.model_dump_json())
    bad_name = 'Unknown' if failure == 'minor_unknown' else 'Host'

    def respond(client, request):
        if isinstance(request, str):
            request = next(r for r in reversed(client.calls) if isinstance(r, dict))
        call = request['call']
        if call == 'part_of_day':
            character = list(initial.characters.values())[clients.index(client)]
            return dict(call='plan', kind='go', intent='Visit', aim='Walk to the stalls.',
                        where=character.where, spot=character.spot)
        if call == 'adjudicate':
            ops = [] if 'Vendor' in load_state(world).people else [
                dict(op='introduce', name='Vendor', where='festival_grounds', spot=None,
                     wants=['Sell fruit'], commitments=[])]
            encounter = dict(mains=list(initial.characters), minor=['Vendor'])
            if failure != 'main_spot':
                encounter['minor'].append(bad_name)
            if failure == 'schema':
                encounter['unexpected'] = True
            return dict(call=call, ops=ops, encounters=[encounter])
        if call == 'scene_round':
            return dict(call=call)
        if call == 'scene_move':
            return dict(call='action', intent='Watch', move='wait', urge=0, action='', say='')
        if call == 'end_of_day':
            return dict(call=call, summary='Visited the stalls.')
        assert call == 'offscreen'
        return dict(call=call, situation_notes={s.id: 'Unchanged.' for s in initial.situations})

    clients = fake_sdk(monkeypatch, respond)
    original = simulation.TickSession
    monkeypatch.setattr(simulation, 'TickSession', lambda w, r: original(w, r, root=ROOT))
    if failure == 'schema':
        with pytest.raises(SessionError, match='Extra inputs are not permitted'):
            asyncio.run(simulation.run_day(world, run))
        assert_fold(world, initial)
        assert read_events(world) == read_scenes(world) == []
        assert rows(run, 'encounter_name_dropped') == []
        assert len(rows(run, 'world_validation_failed')) == 2
        return

    result = asyncio.run(simulation.run_day(world, run))
    assert result.clock.model_dump() == dict(day=2, part='morning')
    assert_fold(world, result)
    assert 'Vendor' in result.people
    assert sum(op.op == 'introduce' for e in read_events(world) for op in e.ops) == 1
    scenes = read_scenes(world)
    assert len(scenes) == 4
    expected = ['agnea', 'hikari', 'Vendor'] if failure == 'main_spot' else ['agnea', 'throne', 'Vendor']
    assert all(scene.participants == expected for scene in scenes)
    drops = rows(run, 'encounter_name_dropped')
    assert len(drops) == 4
    for drop in drops:
        assert drop['call'] == 'adjudicate' and drop['main'] == 'agnea'
        assert drop['name'] == ('throne' if failure == 'main_spot' else bad_name)
        assert drop['error'] == ('encounter mains must share one place and spot' if failure == 'main_spot'
                                 else 'encounter minor must name a person at the same place and spot')
    assert len(rows(run, 'world_validation_failed')) == 4
    world_client = clients[len(initial.characters)]
    assert len([request for request in world_client.calls if isinstance(request, str)]) == 4
    assert all((world / 'memory' / f'{slug}.md').exists() for slug in initial.characters)


def test_offscreen_ids_follow_surviving_events(workspace, monkeypatch):
    world, run = workspace
    reply = dict(call='offscreen', situation_notes={}, events=[
        dict(place='cropdale', ops=[dict(op='move', who='agnea', place='cropdale', spot=None)]),
        dict(place='cropdale', ops=[dict(op='promise', who='Host', what='Help', where='cropdale', day=1, part='night')]),
        dict(place='cropdale', ops=[dict(op='release', who='Host', id='1:0', how='cancelled')]),
    ])
    fake_sdk(monkeypatch, lambda *_: reply)

    async def exercise():
        async with open_agent(workspace, world_agent.OffscreenAgent) as agent:
            events, state, _ = await agent.offscreen(load_state(world), set())
            for event in events:
                commit_event(world, event, authority=Authority('offscreen'))
            return state

    state = asyncio.run(exercise())
    assert [e.id for e in read_events(world)] == [1, 2]
    assert state.people['Host'].commitments == []
    assert len(rows(run, 'event_dropped')) == 1
    assert_fold(world, state)


@pytest.mark.parametrize('drop_closing', [False, True])
def test_scene_bad_release_leaves_winner_for_closing(workspace, monkeypatch, drop_closing):
    world, run = workspace
    targets = []

    def respond(client, request):
        if isinstance(request, str):
            request = next(r for r in reversed(client.calls) if isinstance(r, dict))
        target = request['last_winner']
        targets.append((request['closing'], target))
        if target is None:
            return dict(call='scene_round')
        ops = [dict(op='place', slug='festival_grounds', add_details=['Resolution committed'])]
        if not request['closing'] or drop_closing:
            ops.append(dict(op='release', who='Host', id='missing', how='kept'))
        return dict(call='scene_round', resolution='succeeded', outcome='The attempt succeeds.', ops=ops)

    clients = fake_sdk(monkeypatch, respond)

    class Character:
        turns = 0

        async def act(self, before, note=None):
            self.turns += 1
            return Action(call='action', intent='Try', move='act' if self.turns == 1 else 'wait',
                          urge=2 if self.turns == 1 else 0, action='Agnea tries.' if self.turns == 1 else '', say='')

    character = Character()

    async def exercise():
        async with open_agent(workspace) as agent:
            session = SimpleNamespace(world=agent, characters={'agnea': character}, scene_notes={},
                                      settings=SimpleNamespace(scene_cap=2), trace=TraceWriter(run))
            return await simulation.run_scene(world, session, load_state(world), 'festival_grounds', ['agnea'], [])

    state = asyncio.run(exercise())
    events = read_events(world)
    act = next(e for e in events if e.actor == 'agnea')
    assert character.turns == 2  # the discarded success did not finish the solo attempt
    assert all(target['id'] == act.id for closing, target in targets if target)
    assert targets[-1][0] is True
    resolutions = [e for e in events if e.resolves is not None]
    assert len(resolutions) == (0 if drop_closing else 1)
    if resolutions:
        assert resolutions[0].resolves == act.id and resolutions[0].round == 2
    assert ('Resolution committed' in next(p for p in state.places if p.slug == 'festival_grounds').details) == (not drop_closing)
    drops = rows(run, 'event_dropped')
    assert [d['call'] for d in drops] == (['scene_round', 'closing_resolution'] if drop_closing else ['scene_round'])
    assert all(d['event']['resolves'] == act.id and 'release id must name an existing commitment' in d['error'] for d in drops)
    assert len(clients[0].calls) == (5 if drop_closing else 4)
    assert_fold(world, state)


@pytest.mark.parametrize('call', ['day_start', 'adjudicate'])
def test_world_single_group_is_dropped_atomically(workspace, monkeypatch, call):
    world, run = workspace
    initial = load_state(world)
    ops = [dict(op='place', slug='discarded', add_details=['Must roll back'])]
    if call == 'day_start':
        ops.append(dict(op='open', situation=situation()))
    ops.append(dict(op='move', who='agnea', place='cropdale', spot=None))
    clients = fake_sdk(monkeypatch, lambda *_: dict(call=call, ops=ops))

    async def exercise():
        async with open_agent(workspace) as agent:
            if call == 'day_start':
                return await agent.day_start(initial, [])
            event, encounters, state = await agent.adjudicate(initial, {}, [])
            assert event is None and encounters == []
            return state

    assert asyncio.run(exercise()) == initial
    assert read_events(world) == []
    assert_fold(world, initial)
    assert len(clients[0].calls) == 2 and 'may not commit move' in clients[0].calls[1]
    drop, = rows(run, 'event_dropped')
    assert drop['call'] == call and drop['turn'] == 1 and drop['event']['ops'] == ops


def test_bad_minor_move_drops_only_its_event(workspace, monkeypatch):
    from story_engine.world.models import Event

    world, run = workspace
    state = load_state(world)
    state.people['Baker'] = Person(where='festival_grounds', wants=['Bake'], commitments=[])
    (world / 'genesis.json').write_text(state.model_dump_json())
    act = commit_event(world, Event(id=0, **state.clock.model_dump(), place='festival_grounds',
                                   actor='agnea', type='action', content='Agnea asks.', perceived_by=['agnea'],
                                   scene='1', round=1))
    bad_ops = [dict(op='wants', person='Host', wants=['Changed']),
               dict(op='release', who='Host', id='missing', how='cancelled')]
    reply = dict(call='scene_round', resolution='none', minor_moves={
        'Host': dict(move='act', urge=3, action='Host tries.', ops=bad_ops),
        'Baker': dict(move='act', urge=2, action='Baker tries.',
                      ops=[dict(op='wants', person='Baker', wants=['Help'])])})
    clients = fake_sdk(monkeypatch, lambda *_: reply)

    async def exercise():
        async with open_agent(workspace) as agent:
            event, minors, updated = await agent.round(
                state, read_events(world), place='festival_grounds', main_present=['agnea'],
                minor_present=['Host', 'Baker'], last_winner=dict(id=act.id, actor='agnea'),
                scene='1', round_number=2)
            assert set(minors) == {'Baker'} and updated == state
            commit_event(world, event, authority=Authority('scene_round'))
            commit_event(world, Event(id=0, **state.clock.model_dump(), place='festival_grounds',
                                     actor='Baker', type='action', content=minors['Baker'].action,
                                     perceived_by=['agnea'], scene='1', round=2, ops=minors['Baker'].ops),
                         authority=Authority('person_scene', 'Baker'))

    asyncio.run(exercise())
    assert len(clients[0].calls) == 2
    state = load_state(world)
    assert state.people['Host'].wants == ['Help']
    assert state.people['Baker'].wants == ['Help']
    assert len([e for e in read_events(world) if e.resolves == act.id]) == 1
    drop, = rows(run, 'event_dropped')
    assert drop['event']['actor'] == 'Host' and drop['event']['resolves'] is None
    assert drop['event']['ops'] == bad_ops
    assert_fold(world, state)
