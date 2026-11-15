"""Draws use configured chances and commit only the selected branch, with no model calls."""
import asyncio
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from claude_agent_sdk import ResultMessage

from story_engine.agents import world as world_agent
from story_engine.agents.character import Action
from story_engine.config import load_configs
from story_engine.simulation import run_scene
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state, read_events
from story_engine.world.models import Event

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('resolution,odds,roll,ignored', [
    ('succeeded', 'even', .9, True),
    ('succeeded', 'even', .1, False),
    ('succeeded', 'certain', None, False),
    ('failed', 'even', None, False),
    ('pending', 'even', None, False),
    ('none', 'even', None, False),
])
def test_draw_discards_only_failure_branch_minor_moves(tmp_path, monkeypatch,
                                                       resolution, odds, roll, ignored):
    from story_engine.world.models import Person

    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    state.people['Mabel'] = Person(where='festival_grounds', wants=['Watch the attempt'], commitments=[])
    (world / 'genesis.json').write_text(state.model_dump_json())
    requests, returned, draws = [], [], []
    reply = dict(about=None, call='scene_round', resolution=resolution, odds=odds,
                 outcome='Success outcome.',
                 failure=dict(outcome='Failure outcome.', ops=[
                     dict(op='place', slug='festival_grounds', add_details=['Failure detail'])]),
                 minor_moves={'Mabel': dict(move='act', urge=3, action='Mabel celebrates.',
                     ops=[dict(op='wants', person='Mabel', wants=['Celebrate success'])])})

    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def query(self, request):
            requests.append(json.loads(request))
        async def receive_response(self):
            payload = reply if len(requests) == 2 else dict(call='scene_round')
            if len(requests) != 2 and requests[-1]['last_winner']:
                payload['resolution'] = 'none'
                payload['about'] = None
            yield ResultMessage('success', 1, 1, False, 1, 'fake', structured_output=payload)

    class Character:
        async def act(self, *args, **kwargs):
            return Action(call='action', intent='Try', move='act', urge=2,
                          action='Agnea tries.', say='')

    def draw():
        assert roll is not None, 'must not draw'
        draws.append(roll)
        return roll

    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', Client)
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world, settings.agent_max_turns,
                                          TraceWriter(run), random_source=draw) as agent:
            async def round_(*args, **kwargs):
                result = await agent.round(*args, **kwargs)
                returned.append(result[1])
                return result
            session = SimpleNamespace(world=SimpleNamespace(round=round_),
                characters={'agnea': Character()}, scene_notes={},
                settings=SimpleNamespace(scene_cap=3), trace=TraceWriter(run))
            return await run_scene(world, session, load_state(world), 'festival_grounds',
                                   ['agnea'], ['Mabel'])

    final = asyncio.run(exercise())
    events = read_events(world)
    outcome = next(e for e in events if e.resolves is not None)
    assert outcome.resolution == ('failed' if ignored else resolution)
    assert returned[1] == {} if ignored else 'Mabel' in returned[1]
    assert bool([e for e in events if e.actor == 'Mabel']) is (not ignored)
    assert final.people['Mabel'].wants == (['Watch the attempt'] if ignored else ['Celebrate success'])
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    ignored_rows = [row for row in trace if row['type'] == 'odds_minor_moves_ignored']
    assert draws == ([] if roll is None else [roll])
    if ignored:
        assert outcome.content == 'Failure outcome.'
        assert outcome.ops[0].add_details == ['Failure detail']
        assert 'Failure detail' in next(p.details for p in final.places if p.slug == 'festival_grounds')
        assert not any(op.op == 'wants' for event in events for op in event.ops)
        assert len(ignored_rows) == 1
        assert ignored_rows[0]['turn'] == 2 and ignored_rows[0]['names'] == ['Mabel']
        assert 'minor_moves_not_happened' not in requests[2]
        assert requests[2]['participants']['minor'] == ['Mabel']
        assert any(e.get('resolution') == 'failed' for e in requests[2]['events'])
    else:
        assert not ignored_rows


@pytest.mark.parametrize('mode', ['call', 'session'])
@pytest.mark.parametrize('closing', [False, True])
@pytest.mark.parametrize('odds,roll,resolution,missing,expected', [
    ('even', .9, 'succeeded', False, 'failed'),
    ('even', .1, 'succeeded', False, 'succeeded'),
    ('certain', None, 'succeeded', True, 'succeeded'),
    ('likely', None, 'succeeded', True, 'succeeded'),
    (None, None, 'failed', True, 'failed'),
    ('unlikely', .3, 'succeeded', False, 'succeeded'),  # custom setting, not .25
])
def test_draw_commits_selected_branch(tmp_path, monkeypatch, mode, closing, odds, roll,
                                      resolution, missing, expected):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    root = tmp_path / 'root'
    shutil.copytree(ROOT / 'prompts', root / 'prompts')
    (root / 'config').mkdir()
    settings_data = yaml.safe_load((ROOT / 'config/settings.yaml').read_text())
    settings_data['odds']['unlikely'] = .8
    (root / 'config/settings.yaml').write_text(yaml.safe_dump(settings_data))
    requests, draws = [], []
    reply = dict(about=None, call='scene_round', resolution=resolution, outcome='Success outcome.',
                 ops=[dict(op='place', slug='festival_grounds', add_details=['Success detail'])])
    if odds is not None:
        reply['odds'] = odds
    if not missing:
        reply['failure'] = dict(outcome='Failure outcome.', ops=[
            dict(op='place', slug='festival_grounds', add_details=['Failure detail'])])

    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def query(self, request):
            requests.append(request)
        async def receive_response(self):
            payload = reply if 'World validation failed' in requests[-1] or json.loads(requests[-1]).get('last_winner') else dict(call='scene_round')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', structured_output=payload)

    def random_source():
        assert roll is not None, 'must not draw'
        draws.append(roll)
        return roll

    class Character:
        async def act(self, *args, **kwargs):
            return Action(call='action', intent='Try', move='act', urge=2, action='Tries.', say='')

    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', Client)
    models, settings = load_configs()
    models.world.schema_mode = mode
    async def exercise():
        async with world_agent.WorldAgent(root, run, world, models.world, settings.agent_max_turns,
                                          TraceWriter(run), random_source=random_source) as agent:
            session = SimpleNamespace(world=agent, characters={'agnea': Character()}, scene_notes={},
                                      settings=SimpleNamespace(scene_cap=1 if closing else 3), trace=TraceWriter(run))
            return await run_scene(world, session, load_state(world), 'festival_grounds', ['agnea'], [])
    state = asyncio.run(exercise())
    event = next(e for e in read_events(world) if e.resolves is not None)
    selected_failure = roll is not None and expected == 'failed'
    label = 'Failure' if selected_failure else 'Success'
    assert event.resolution == expected and event.content == f'{label} outcome.'
    assert event.odds == odds and 'odds' not in event.agent_view()
    assert event.ops[0].add_details == [f'{label} detail']
    details = next(p.details for p in state.places if p.slug == 'festival_grounds')
    assert f'{label} detail' in details
    assert ('Success detail' if selected_failure else 'Failure detail') not in details
    assert state == load_state(world)
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    rolls = [r for r in trace if r['type'] == 'odds_roll']
    if roll is not None:
        assert draws == [roll] and len(rolls) == 1
        assert {k: rolls[0][k] for k in ('turn', 'odds', 'chance', 'roll', 'result')} == dict(
            turn=2, odds=odds, chance=settings_data['odds'][odds], roll=roll, result=expected)
    else:
        assert not draws and not rolls
    if odds == 'likely':
        assert len(requests) == 3
        assert 'require failure' in requests[-1]
        assert any(r['type'] == 'odds_failure_missing' for r in trace)


def test_historical_event_and_reply(tmp_path):
    event = Event(id=1, day=1, part='morning', place='cropdale', actor='world',
                  type='world', content='Fact.', perceived_by=[])
    old = event.model_dump(exclude={'odds'})
    world = tmp_path / 'world'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    before = load_state(world)
    with (world / 'events.jsonl').open('a') as stream:
        stream.write(json.dumps(old) + '\n')
    assert read_events(world)[-1].odds is None
    assert load_state(world) == before
    world_agent.RoundResolution.model_validate(dict(call='scene_round', resolution='succeeded'))


@pytest.mark.parametrize('resolution', ['succeeded', 'pending', 'none'])
def test_odds_validation_and_failure_authority(tmp_path, monkeypatch, resolution):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    requests = []
    bad_ops = [dict(op='goals', main='agnea', goals=['Forbidden'])]
    reply = dict(about=None, call='scene_round', resolution=resolution, outcome='Success.', odds='even',
                 failure=dict(outcome='Failure.', ops=bad_ops))
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def query(self, request):
            requests.append(request)
        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake', structured_output=reply)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', Client)
    models, settings = load_configs()
    def draw():
        assert resolution == 'succeeded'
        return .9
    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world, settings.agent_max_turns,
                                          TraceWriter(run), random_source=draw) as agent:
            return await agent.round(load_state(world), [], place='festival_grounds',
                main_present=['agnea'], minor_present=[], last_winner=dict(id=42, actor='agnea'),
                scene='1', round_number=2)
    before = load_state(world)
    event, _, state = asyncio.run(exercise())
    assert state == before and load_state(world) == before
    if resolution == 'succeeded':
        assert event is None and len(requests) == 2
        assert 'event_dropped' in (run / 'trace.jsonl').read_text()
    else:
        assert event.resolution == resolution and len(requests) == 1
        assert 'odds_roll' not in (run / 'trace.jsonl').read_text()


def test_live_odds_required_and_failure_shape():
    from pydantic import ValidationError
    import jsonschema
    reply = dict(call='scene_round', resolution='succeeded', outcome='A fact.')
    with pytest.raises(ValidationError, match='require odds'):
        world_agent.WinningRoundReply.model_validate(reply)
    schema = world_agent.WinningRoundReply.model_json_schema()
    for fields in ({}, {'odds': None}, {'odds': 'likely'}, {'odds': 'even', 'failure': None}):
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({**reply, **fields}, schema)
    for outcome in ('', 'x' * 281):
        with pytest.raises(ValidationError):
            world_agent.WinningRoundReply.model_validate(dict(reply, odds='even', failure=dict(outcome=outcome, ops=[])))
