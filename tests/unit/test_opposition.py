"""Opposition is reference data; fake SDK calls exercise both schema modes."""
import asyncio
import json
import shutil
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest
from pydantic import ValidationError

from story_engine.agents import world as world_agent
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state, read_events
from story_engine.world.models import Event, Person, WorldState
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
    (world / 'genesis.json').write_text(state.model_dump_json())
    return world, run, state


def traces(run, kind):
    return [row for row in map(json.loads, (run / 'trace.jsonl').read_text().splitlines())
            if row['type'] == kind]


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
