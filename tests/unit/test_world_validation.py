"""Deterministic D2/D28 guards exercised through a fake World SDK session."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from pydantic import ValidationError

from story_engine.agents import world as world_agent
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import commit_event, load_state
from story_engine.world.models import Person
from story_engine.world.permissions import Authority
from world_replies import round_reply

ROOT = Path(__file__).resolve().parents[2]


def _offscreen_reply(state, events=None, situation_notes=None):
    return dict(call='offscreen', events=events or [],
               situation_notes=situation_notes or {s.id: 'Unchanged.' for s in state.situations})


def _fake_client(replies, requests):
    class FakeClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            requests.append(request)

        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=next(replies))

    return FakeClient


@pytest.mark.parametrize('case,scene,last_winner,content,event_type', [
    ('tick', False, None, 'The wind rises.', 'world'),
    ('subject', True, None, 'Throné rises.', 'world'),
    ('subject', True, None, "throne's hands move.", 'world'),
    ('subject', True, None, 'Agnea nods.', 'world'),
    ('subject', True, None, 'The Dancer smiles.', 'world'),
    ('quoted', True, None, '"Agnea! Over here," the boy calls.', 'world'),
    ('quoted', True, None, '“Agnea! Over here,” the boy calls.', 'world'),
    ('object', True, None, 'Gus hands Agnea a basket.', 'world'),
    ('speech', True, None, 'Agnea! There you are.', 'speech'),
    ('banner', True, None, "The Dancer's Blessing banner glows.", 'world'),
])
@pytest.mark.parametrize('actor', ['world', 'Gus'])
def test_world_content_accepted_with_no_text_judgment(tmp_path, monkeypatch, case, scene, last_winner, content, event_type, actor):
    """D27: code judges only schema and data references, never the wording of event content.
    A main character's name may start or appear anywhere in the content without being rejected."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    if scene:
        event = dict(place='festival_grounds', actor=actor, type=event_type,
                     content=content, perceived_by=['agnea'])
        last_winner = {'id': 42, 'actor': 'agnea', 'round': 1}
        reply = round_reply({'last_winner': last_winner}, outcome=event)
    else:
        event = dict(place='festival_grounds', content=content)
        reply = _offscreen_reply(state, events=[event])
    replies = iter([json.dumps(reply)])
    requests = []

    class FakeClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            requests.append(request)

        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=next(replies))

    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', FakeClient)
    models, settings = load_configs()

    async def exercise():
        agent_type = world_agent.WorldAgent if scene else world_agent.OffscreenAgent
        async with agent_type(ROOT, run, world, models.world,
                              settings.agent_max_turns, TraceWriter(run)) as agent:
            if scene:
                return await agent.round(state, [], place='festival_grounds',
                                         main_present=['agnea', 'throne'], minor_present=[],
                                         last_winner=last_winner, scene="1", round_number=2)
            return await agent.offscreen(state, {s.id for s in state.situations if s.status == 'open'})

    result = asyncio.run(exercise())
    failures = [row for row in map(json.loads, (run / 'trace.jsonl').read_text().splitlines())
                if row['type'] == 'world_validation_failed']
    assert len(requests) == 1 and not failures
    if scene:
        outcome, _minor_moves, _state = result
        assert outcome.content == content
    else:
        events, _updated, _notes = result
        assert events[0].content == content
    assert state == load_state(world)


def test_offscreen_reply_omitting_people_keeps_them(tmp_path, monkeypatch):
    """People persist (D21): an offscreen reply that leaves someone out doesn't erase them."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    state.people['Gus'] = Person(where='festival_grounds', wants=['Save the contest'], commitments=[])
    reply = _offscreen_reply(state)
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', _fake_client(iter([json.dumps(reply)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.OffscreenAgent(ROOT, run, world, models.world,
                                             settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.offscreen(state, {s.id for s in state.situations if s.status == 'open'})

    _events, updated, _notes = asyncio.run(exercise())
    assert updated.people['Gus'].wants == ['Save the contest']




@pytest.fixture
def workspace(tmp_path):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    return world, run


def call_agent(workspace, monkeypatch, replies, *, scene=False, state=None, winner=None, retries=None, closing=False):
    world, run = workspace
    state = state or load_state(world)
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', _fake_client(iter(map(json.dumps, replies)), requests))
    models, settings = load_configs()
    role = models.world if retries is None else models.world.model_copy(update={'retries': retries})
    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, role, settings.agent_max_turns, TraceWriter(run)) as agent:
            if scene:
                return await agent.round(state, [], place='festival_grounds', main_present=['agnea', 'throne'],
                                         minor_present=list(state.people), last_winner=winner,
                                         scene='1', round_number=2, closing=closing)
            return await agent.adjudicate(state, {'agnea': {'kind': 'attempt'}}, [])
    return exercise, requests


@pytest.mark.parametrize('field,value', [
    ('verdicts', {'agnea': {'status': 'settled', 'outcome': 'A result'}}),
    ('verdicts', {'agnea': {'status': 'staged'}}),
    ('outcome', 'A result'), ('situation_updates', [{'id': 'x', 'status': 'resolved'}]),
])
def test_encounter_shape_has_no_result_authority(field, value):
    with pytest.raises(ValidationError):
        world_agent.AdjudicateReply.model_validate({'call': 'adjudicate', field: value})


@pytest.mark.parametrize('bad', [
    dict(mains=['agnea', 'throne'], minor=[]),
    dict(mains=['stranger'], minor=[]),
    dict(mains=['agnea'], minor=['Unknown']),
    dict(mains=['agnea'], minor=['Host']),
])
def test_encounter_references_and_same_spot_retry(workspace, monkeypatch, bad):
    state = load_state(workspace[0])
    state.characters['throne'].spot = 'stage'
    state.people['Host'] = Person(where='festival_grounds', spot='stage', wants=['Watch'], commitments=[])
    exercise, requests = call_agent(workspace, monkeypatch,
                                    [dict(call='adjudicate', encounters=[bad]), dict(call='adjudicate')], state=state)
    event, encounters, updated = asyncio.run(exercise())
    assert len(requests) == 2 and encounters == []
    assert updated == state and event.ops == []


def test_encounter_introduces_and_normalizes_people_without_writing(workspace, monkeypatch):
    state = load_state(workspace[0])
    reply = dict(call='adjudicate', ops=[dict(op='introduce', name='Merchant Tam', where='festival_grounds',
                                            wants=['Sell fruit'], commitments=[])],
                 encounters=[dict(mains=['agnea'], minor=['  MÉRCHANT_tam  '])])
    exercise, requests = call_agent(workspace, monkeypatch, [reply])
    event, encounters, updated = asyncio.run(exercise())
    assert len(requests) == 1 and encounters[0].minor == ['Merchant Tam']
    assert 'Merchant Tam' in updated.people and load_state(workspace[0]) == state
    commit_event(workspace[0], event, authority=Authority('encounter'))
    assert load_state(workspace[0]) == updated


@pytest.mark.parametrize('op', [dict(op='move', who='agnea', place='cropdale', spot=None),
                                 dict(op='situation', id='festival_textile_theft', status='resolved')])
def test_encounter_rejects_ops_outside_its_authority(workspace, monkeypatch, op):
    exercise, requests = call_agent(workspace, monkeypatch,
                                    [dict(call='adjudicate', ops=[op]), dict(call='adjudicate')])
    asyncio.run(exercise())
    assert len(requests) == 2 and 'may not commit' in requests[1]


@pytest.mark.parametrize('retries', [None, 3])
@pytest.mark.parametrize('recover', [False, True])
def test_adjudicate_retry_budget(workspace, monkeypatch, retries, recover):
    count = (1 if retries is None else retries) + 1
    replies = [{}] * (count - 1) + [dict(call='adjudicate') if recover else {}]
    exercise, requests = call_agent(workspace, monkeypatch, replies, retries=retries)
    if recover:
        event, encounters, _ = asyncio.run(exercise())
        assert event.ops == [] and encounters == []
    else:
        with pytest.raises(world_agent.SessionError, match='World validation failed after'):
            asyncio.run(exercise())
    assert len(requests) == count


@pytest.mark.parametrize('resolution', ['succeeded', 'failed', 'pending', 'none'])
def test_scene_resolves_only_the_supplied_winning_act(workspace, monkeypatch, resolution):
    winner = dict(id=42, actor='throne', round=1)
    good = dict(call='scene_round', resolution=resolution, outcome='An unchecked fact.')
    exercise, requests = call_agent(workspace, monkeypatch, [good],
                                    scene=True, winner=winner)
    event, _, _ = asyncio.run(exercise())
    assert len(requests) == 1 and event.resolves == 42 and event.of == 'throne'
    assert event.actor == 'world' and event.scene == '1' and event.round == 1
    assert event.resolution == resolution


@pytest.mark.parametrize('fields', [dict(outcome='No winner'), dict(resolves=42), dict(resolves=None),
                                    dict(actor='agnea'), dict(scene='forged'), dict(round=99), dict(of='throne')])
def test_scene_metadata_and_resolution_schema(fields):
    with pytest.raises(ValidationError):
        world_agent.RoundResolution.model_validate(dict(call='scene_round', **fields))


def test_scene_minor_references_introductions_and_name_matching(workspace, monkeypatch):
    state = load_state(workspace[0])
    state.people['garud'] = Person(where='festival_grounds', wants=['Watch'], commitments=[])
    move = dict(move='wait', urge=0, action='', say='')
    good = dict(call='scene_round', minor_moves={'Garud': move, 'Host': move},
                ops=[dict(op='introduce', name='Host', where='festival_grounds', wants=['Help'], commitments=[])])
    exercise, requests = call_agent(workspace, monkeypatch,
                                    [dict(call='scene_round', minor_moves={'Unknown': move}), good],
                                    scene=True, state=state)
    event, minors, updated = asyncio.run(exercise())
    assert len(requests) == 2 and set(minors) == {'garud', 'Host'}
    assert updated.people['Host'].wants == ['Help']
    assert json.loads(requests[0])['people'] == {'garud': state.people['garud'].model_dump()}
    assert load_state(workspace[0]).people == {}
    assert event.ops[0].op == 'introduce'


@pytest.mark.parametrize('resolution', ['pending', 'none'])
def test_closing_resolution_requires_final_result_and_no_bids(workspace, monkeypatch, resolution):
    reply = dict(call='scene_round', resolution=resolution,
                 minor_moves={'Host': dict(move='wait', urge=0)} if resolution == 'none' else {})
    exercise, _ = call_agent(workspace, monkeypatch, [reply, reply], scene=True,
                             winner=dict(id=42, actor='agnea', round=1), closing=True)
    with pytest.raises(world_agent.SessionError, match='closing resolution'):
        asyncio.run(exercise())


@pytest.mark.parametrize('closing', [False, True])
@pytest.mark.parametrize('supplied_id', [None, 42, 999])
def test_model_supplied_resolves_is_a_schema_error(workspace, monkeypatch, closing, supplied_id):
    good = dict(call='scene_round', resolution='none', ops=[])
    bad = dict(good, resolves=supplied_id)
    with pytest.raises(ValidationError) as caught:
        world_agent.RoundResolution.model_validate(bad)
    assert any(error['loc'] == ('resolves',) and error['type'] == 'extra_forbidden'
               for error in caught.value.errors())
    exercise, requests = call_agent(workspace, monkeypatch, [bad, good], scene=True,
                                    winner=dict(id=42, actor='agnea', round=1), closing=closing)
    event, _, _ = asyncio.run(exercise())
    assert len(requests) == 2 and 'Extra inputs are not permitted' in requests[1]
    assert event.resolves == 42 and event.resolution == 'none'


@pytest.mark.parametrize('winner,resolution', [(None, 'none'), (dict(id=42, actor='agnea', round=1), None)])
def test_scene_resolution_requires_exactly_an_outstanding_winner(workspace, monkeypatch, winner, resolution):
    reply = dict(call='scene_round', resolution=resolution)
    exercise, _ = call_agent(workspace, monkeypatch, [reply, reply], scene=True, winner=winner)
    with pytest.raises(world_agent.SessionError, match='winning act'):
        asyncio.run(exercise())
