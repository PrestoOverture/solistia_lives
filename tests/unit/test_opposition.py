"""Opposition is reference data; fake SDK calls exercise both schema modes."""
import asyncio
import json
import shutil
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from story_engine import simulation
from story_engine.agents import initializer, world as world_agent
from story_engine.agents.sdk import SessionError
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import commit_event, load_state, read_events
from story_engine.world.models import Event, Person, Situation, WorldState
from story_engine.world.ops import OPS, reduce_ops
from story_engine.world.permissions import Authority, validate_ops
from test_day_start import fake_sdk, situation

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def workspace(tmp_path):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    state.people['Host'] = Person(where='festival_grounds', wants=['Keep the gate closed'], commitments=[])
    state.situations[0].people = ['Host']
    state.situations[0].opposed_by = ['Host']
    state.situations[0].heard = 'The host is keeping the gate closed.'
    (world / 'genesis.json').write_text(state.model_dump_json())
    return world, run, state


def traces(run, kind):
    return [row for row in map(json.loads, (run / 'trace.jsonl').read_text().splitlines())
            if row['type'] == kind]


@pytest.mark.parametrize('case,error', [
    ('valid', None),
    ('empty', 'non-empty at_stake'),
    ('goal', 'copy one of'),
    ('untouched', 'touched mains'),
    ('person', 'touched mains'),
    ('unknown', 'touched mains'),
    ('place', 'where and spot'),
    ('spot', 'where and spot'),
    ('day', 'due.day >= 2'),
    ('heard_null', 'non-null heard'),
    ('heard_long', 'at most 200 characters'),
    ('source_unknown', "heard_from must name one of this situation's people"),
    ('source_away', "heard_from must be at a touched main's where"),
    ('source_local', None),
])
@pytest.mark.parametrize('corrected', [False, True])
def test_starting_opposition_validation(workspace, monkeypatch, case, error, corrected):
    world, run, state = workspace
    (run / 'scene_context.md').write_text('## Context\nA festival.')
    for member in [*state.characters.values(), *state.people.values()]:
        member.where, member.spot = 'cropdale', None
    state.places[0].slug = 'cropdale'
    target = state.situations[0]
    target.touches = ['agnea']
    target.at_stake = {'agnea': state.characters['agnea'].goals[0]}
    target.due.day = 2
    state.people['Courier'] = Person(where='cropdale', wants=['Deliver news'], commitments=[])
    target.people.append('Courier')
    valid = state.model_dump(exclude={'clock'})
    bad = deepcopy(valid)
    item = bad['situations'][0]
    if case == 'empty':
        item['at_stake'] = {}
    elif case == 'goal':
        item['at_stake']['agnea'] += ' '
    elif case in {'untouched', 'person', 'unknown'}:
        main = {'untouched': 'throne', 'person': 'Host', 'unknown': 'missing'}[case]
        item['at_stake'] = {main: state.characters['throne'].goals[0]}
    elif case == 'place':
        bad['people']['Host']['where'] = 'festival_grounds'
        bad['places'].append(dict(slug='festival_grounds', details=[]))
    elif case == 'spot':
        bad['people']['Host']['spot'] = 'tavern'
    elif case == 'day':
        item['due']['day'] = 1
    elif case == 'heard_null':
        item['heard'] = None
    elif case == 'heard_long':
        item['heard'] = 'x' * 201
    elif case == 'source_unknown':
        item['heard_from'] = 'Stranger'
    elif case == 'source_away':
        item['heard_from'] = 'Courier'
        bad['people']['Courier']['where'] = 'festival_grounds'
        bad['places'].append(dict(slug='festival_grounds', details=[]))
    elif case == 'source_local':
        item['heard_from'] = 'Courier'
        # Only one of the touched mains needs to share the source's place.
        item['touches'] = ['throne', 'agnea']
        bad['characters']['throne']['where'] = 'festival_grounds'
        bad['places'].append(dict(slug='festival_grounds', details=[]))

    def respond(client, request):
        return deepcopy(valid if corrected and len(client.calls) == 2 else bad)

    clients = fake_sdk(monkeypatch, respond)
    from story_engine.agents import character
    monkeypatch.setattr(initializer, 'ClaudeSDKClient', character.ClaudeSDKClient)
    monkeypatch.setattr(initializer, 'record_api_host', lambda *_: None)
    models, settings = load_configs()
    models.initializer.retries = 1

    def exercise():
        return asyncio.run(initializer.starting_state(
            ROOT, run, list(state.characters), 'cropdale', 'A festival',
            models.initializer, settings.agent_max_turns, TraceWriter(run)))

    if error and not corrected:
        with pytest.raises(SessionError, match=error):
            exercise()
    else:
        result = exercise()
        assert result.situations[0].at_stake == target.at_stake
        assert result.people['Host'].spot == result.characters['agnea'].spot == 'village_square'
    assert len(clients[0].calls) == (2 if error else 1)
    if error:
        assert error in clients[0].calls[1]
        assert all(error in row['error'] for row in traces(run, 'state_validation_failed'))


def test_at_stake_requires_opposition(workspace):
    data = workspace[2].situations[0].model_dump()
    assert Situation.model_validate(data).at_stake == {}
    data.update(opposed_by=[], at_stake={'agnea': 'Visit'})
    with pytest.raises(ValidationError, match='at_stake requires non-empty opposed_by'):
        Situation.model_validate(data)


@pytest.mark.parametrize('source', [None, 'Host'])
@pytest.mark.parametrize('touches', [['agnea'], ['agnea', 'throne']])
@pytest.mark.parametrize('history', ['fresh', 'heard', 'unrelated'])
def test_starting_heard_precedes_and_is_perceived_by_first_plans(
        workspace, monkeypatch, source, touches, history):
    world, run, state = workspace
    target = state.situations[0]
    target.touches, target.heard_from = touches, source
    (world / 'genesis.json').write_text(state.model_dump_json())
    if history != 'fresh':
        commit_event(world, Event(
            id=0, **state.clock.model_dump(), place=state.characters[touches[0]].where,
            actor=source or 'world', type='world',
            content=target.heard if history == 'heard' else 'The morning bell rings.',
            perceived_by=touches, about=target.id if history == 'heard' else None))
    planned = set()

    def respond(client, request):
        call = request['call']
        if call == 'part_of_day':
            slug = ('agnea', 'throne')[clients.index(client)]
            if slug not in planned:
                facts = [e for e in request['perceived'] if e['content'] == target.heard]
                assert len(facts) == int(history != 'unrelated' and slug in touches)
                planned.add(slug)
            return dict(call='plan', kind='go', intent='Explore', aim='Stay here.',
                        where='festival_grounds', spot=None)
        if call == 'scene_move':
            return dict(call='action', move='wait', urge=0, intent='Wait', action='', say='')
        if call in {'adjudicate', 'scene_round'}:
            return dict(call=call)
        if call == 'offscreen':
            return dict(call=call, settle={id: 'dropped' for id in request.get('due_now', [])},
                        situation_notes={s.id: 'Unchanged.' for s in load_state(world).situations
                                         if s.status == 'open'})
        assert call == 'end_of_day'
        return dict(call=call, summary='The gate stays closed.')

    clients = fake_sdk(monkeypatch, respond)
    original_session = simulation.TickSession
    monkeypatch.setattr(simulation, 'TickSession', lambda w, r: original_session(w, r, root=ROOT))
    asyncio.run(simulation.run_day(world, run))

    assert planned == set(state.characters)
    events = read_events(world)
    facts = [e for e in events if e.content == target.heard]
    assert len(facts) == int(history != 'unrelated')
    if facts:
        fact, = facts
        assert fact.perceived_by == touches and fact.about == target.id
        assert fact.actor == (source or 'world') and fact.type == 'world'
        assert fact.place == state.characters[touches[0]].where
        assert (fact.day, fact.part, fact.scene, fact.round) == (1, 'morning', None, None)
        assert fact.ops == []
        assert fact.id < min(e.id for e in events if e.type == 'plan')


@pytest.mark.parametrize('fields', [
    {'at_stake': {'agnea': 'Visit'}},
    {'opposed_by': ['Host'], 'at_stake': {'agnea': 'Visit'}},
    {'at_stake': {}},
])
def test_at_stake_op_round_trip_and_day_start_permission(workspace, fields):
    state = workspace[2]
    ops = OPS.validate_python([dict(op='situation', id=state.situations[0].id, **fields)])
    ops = OPS.validate_json(OPS.dump_json(ops))
    updated = reduce_ops(state, ops, event_id=1)
    assert updated.situations[0].at_stake == fields['at_stake']
    assert state.situations[0].at_stake == {}
    event = Event(id=1, **state.clock.model_dump(), place='festival_grounds', actor='world',
                  type='world', content='', perceived_by=[], ops=ops)
    assert validate_ops(state, event, Authority('day_start')) == updated


def test_opposition_must_name_same_situation_people(workspace):
    _, _, state = workspace
    # Host exists globally but isn't in this situation.
    data = state.model_dump()
    data['situations'][0]['people'] = []
    with pytest.raises(ValidationError, match='opposed_by'):
        WorldState.model_validate(data)
    with pytest.raises(ValidationError, match='opposed_by'):
        world_agent.DayStartSituation.model_validate(dict(situation(), opposed_by=['Host']))
    with pytest.raises(ValidationError, match='opposed_by'):
        reduce_ops(state, OPS.validate_python([
            dict(op='situation', id=state.situations[0].id, opposed_by=['Stranger'])]), event_id=1)


def test_people_update_clears_at_stake_when_all_opposers_removed(workspace):
    state = workspace[2]
    target = state.situations[0]
    target.at_stake = {'agnea': state.characters['agnea'].goals[0]}
    ops = OPS.validate_python([dict(op='situation', id=target.id, people=[])])

    updated = reduce_ops(state, ops, event_id=1)

    assert updated.situations[0].opposed_by == []
    assert updated.situations[0].at_stake == {}
    assert target.opposed_by == ['Host']
    assert target.at_stake == {'agnea': state.characters['agnea'].goals[0]}


def test_people_update_prunes_opposition_and_replays(workspace):
    world, _, state = workspace
    ops = OPS.validate_python([dict(op='situation', id=state.situations[0].id, people=[])])
    updated = reduce_ops(state, ops, event_id=1)
    assert updated.situations[0].opposed_by == []
    assert state.situations[0].opposed_by == ['Host']
    event = Event(id=1, **state.clock.model_dump(), place='festival_grounds', actor='world',
                  type='world', content='The host departs.', perceived_by=[], ops=ops)
    (world / 'events.jsonl').write_text(event.model_dump_json() + '\n')
    assert load_state(world) == updated


@pytest.mark.parametrize('genesis', [False, True])
def test_legacy_state_and_events_load_and_fold_without_opposition(tmp_path, genesis):
    world = tmp_path / 'world'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    if not genesis:
        (world / 'genesis.json').unlink()
    original = load_state(world)
    assert all(s.opposed_by == [] for s in original.situations)
    if genesis:
        # A historical situation op also has no opposed_by field.
        row = dict(id=1, day=1, part='morning', place='festival_grounds', actor='world',
                   type='world', content='Settled.', perceived_by=[],
                   ops=[dict(op='situation', id=original.situations[0].id, status='resolved')])
        (world / 'events.jsonl').write_text(json.dumps(row) + '\n')
        assert load_state(world).situations[0].status == 'resolved'
        assert read_events(world)[0].ops[0].opposed_by is None
        assert all(s.opposed_by == [] for s in load_state(world).situations)


@pytest.mark.parametrize('call,allowed', [('scene_round', True), ('day_start', True),
                                        ('offscreen', False), ('encounter', False),
                                        ('person_scene', False), ('code', False)])
def test_opposition_update_authority(workspace, call, allowed):
    _, _, state = workspace
    event = Event(id=1, **state.clock.model_dump(), place='festival_grounds', actor='world',
                  type='world', content='', perceived_by=[], scene='1', resolves=1, resolution='none',
                  ops=OPS.validate_python([dict(op='situation', id=state.situations[0].id, opposed_by=[])]))
    authority = Authority(call, parts_of_day=('morning', 'afternoon', 'evening', 'night'))
    if allowed:
        assert validate_ops(state, event, authority).situations[0].opposed_by == []
    else:
        with pytest.raises(ValueError, match='may not commit'):
            validate_ops(state, event, authority)


@pytest.mark.parametrize('mode', ['call', 'session'])
@pytest.mark.parametrize('case', ['missing', 'corrected', 'existing', 'settled', 'opens_nothing', 'updated'])
def test_day_start_opposition_retry_and_fallback(workspace, monkeypatch, mode, case):
    world, run, state = workspace
    if case != 'existing':
        state.situations[0].opposed_by = []
    if case == 'settled':
        state.situations[0].opposed_by = ['Host']
        state.situations[0].status = 'resolved'
    (world / 'genesis.json').write_text(state.model_dump_json())

    def respond(client, request):
        new = dict(situation(), people=['Host'])
        if case == 'corrected' and len(client.calls) == 2:
            new['opposed_by'] = ['Host']
        ops = [] if case == 'opens_nothing' else [dict(op='open', situation=new)]
        if case == 'updated':
            ops.insert(0, dict(op='situation', id=state.situations[0].id, opposed_by=['Host']))
        return dict(call='day_start', ops=ops)

    clients = fake_sdk(monkeypatch, respond)
    models, settings = load_configs()
    models.world.schema_mode, models.world.retries = mode, 1

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world, settings.agent_max_turns,
                                           TraceWriter(run)) as agent:
            return await agent.day_start(state, [])

    updated = asyncio.run(exercise())
    retry = case in {'missing', 'corrected', 'settled'}
    assert len(clients[0].calls) == (2 if retry else 1)
    assert len(traces(run, 'world_validation_failed')) == int(retry)
    if retry:
        assert 'opposed_by' in clients[0].calls[1]
    missing = traces(run, 'opposition_missing')
    assert len(missing) == int(case in {'missing', 'settled'})
    if missing:
        assert missing[0]['call'] == 'day_start' and missing[0]['turn'] == 1
    assert len(updated.situations) == len(state.situations) + int(case != 'opens_nothing')
    if case in {'corrected', 'existing', 'updated'}:
        assert any(s.status == 'open' and s.opposed_by for s in updated.situations)


@pytest.mark.parametrize('mode', ['call', 'session'])
@pytest.mark.parametrize('closing', [False, True])
@pytest.mark.parametrize('case', ['contested', 'corrected', 'absent', 'other', 'null', 'resolved', 'failed'])
def test_scene_contested_schema_and_session_retry(workspace, monkeypatch, mode, closing, case):
    world, run, state = workspace
    target = state.situations[0].id
    about = state.situations[1].id if case == 'other' else None if case == 'null' else target
    if case == 'resolved':
        state.situations[0].status = 'resolved'
    minors = [] if case == 'absent' else ['Host']
    contested = [] if case in {'absent', 'resolved'} else [target]
    resolution = 'failed' if case == 'failed' else 'succeeded'

    def respond(client, request):
        reply = dict(call='scene_round', resolution=resolution, outcome='The attempt is resolved.',
                     about=about, odds='certain', ops=[])
        if case == 'corrected' and (mode == 'call' or len(client.calls) == 2):
            reply.update(odds='likely', failure=dict(outcome='The attempt fails.', ops=[]))
        if len(client.calls) == 1:
            assert request.get('contested', []) == contested
            assert ('contested' in request) == bool(contested)
        else:
            assert 'contested' in request and 'certain' in request
        if mode == 'call':
            schema = client.options.output_format['schema']
            invalid = dict(reply, about=target, resolution='succeeded', odds='certain')
            if contested:
                with pytest.raises(jsonschema.ValidationError):
                    jsonschema.validate(invalid, schema)
                for odds in ['likely', 'even', 'unlikely']:
                    jsonschema.validate(dict(invalid, odds=odds,
                        failure=dict(outcome='The attempt fails.', ops=[])), schema)
            else:
                jsonschema.validate(invalid, schema)
            # The fake provider returns an allowed reply after demonstrating schema rejection.
            if case == 'contested':
                reply.update(odds='even', failure=dict(outcome='The attempt fails.', ops=[]))
            jsonschema.validate(reply, schema)
        return deepcopy(reply)

    clients = fake_sdk(monkeypatch, respond)
    models, settings = load_configs()
    models.world.schema_mode, models.world.retries = mode, 1

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world, settings.agent_max_turns,
                                           TraceWriter(run), random_source=lambda: 0) as agent:
            return await agent.round(state, [], place='festival_grounds', main_present=['agnea'],
                minor_present=minors, last_winner=dict(id=1, actor='agnea'), scene='1',
                round_number=2, closing=closing)

    event, _, _ = asyncio.run(exercise())
    retry = mode == 'session' and case in {'contested', 'corrected'}
    assert len(clients[0].calls) == (2 if retry else 1)
    assert len(traces(run, 'world_validation_failed')) == int(retry)
    warnings = traces(run, 'odds_certain_contested')
    assert len(warnings) == int(mode == 'session' and case == 'contested')
    if warnings:
        assert warnings[0]['about'] == target and warnings[0]['turn'] == 1
    assert event.about == about and event.resolution == resolution
    assert event.odds == ('likely' if case == 'corrected' else
                          'even' if mode == 'call' and case == 'contested' else 'certain')
