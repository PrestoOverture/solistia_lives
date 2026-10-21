"""Deterministic D2 guards exercised through a fake World SDK session."""

import asyncio
import copy
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from story_engine.agents import world as world_agent
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('case,scene,last_winner,content,error,event_type', [
    ('tick', False, None, 'The wind rises.', None, 'world'),
    ('subject', True, None, 'Throné rises.', 'Throné rises.', 'world'),
    ('subject', True, None, "throne's hands move.", "throne's hands move.", 'world'),
    ('subject', True, None, 'Agnea nods.', 'Agnea nods.', 'world'),
    ('subject', True, None, 'The Dancer smiles.', 'The Dancer smiles.', 'world'),
    ('subject', True, None, 'The wind rises. Throné’s hands move.', 'Throné’s hands move.', 'world'),
    ('quoted', True, None, '"Agnea! Over here," the boy calls.', None, 'world'),
    ('quoted', True, None, '“Agnea! Over here,” the boy calls.', None, 'world'),
    ('subject', True, None, '"Hello," Agnea nods.', 'Agnea nods.', 'world'),
    ('object', True, None, 'Gus hands Agnea a basket.', None, 'world'),
    ('speech', True, None, 'Agnea! There you are!', None, 'speech'),
    ('subject', True, None, 'Agnea nods.', 'M2 subject check', 'action'),
    ('subject', True, None, 'Throné looks up.', 'M2 subject check', 'world'),
])
@pytest.mark.parametrize('actor', ['world', 'Gus'])
def test_world_d2_validation(tmp_path, monkeypatch, case, scene, last_winner, content, error, event_type, actor):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor=actor, type='world',
                 content='Gus hands Agnea a basket.', perceived_by=['agnea'])
    if scene:
        good = dict(call='scene_round', outcome=event, minor_moves={})
    else:
        good = dict(call='part_of_day', events=[event], state=state.model_dump(exclude={'clock'}),
                    situation_notes={s.id: 'Unchanged.' for s in state.situations})
    first = copy.deepcopy(good)
    bad_event = first['outcome'] if scene else first['events'][0]
    bad_event['content'] = content
    bad_event['type'] = event_type
    replies = iter([json.dumps(first), json.dumps(good)])
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
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            if scene:
                return await agent.round(state, [], place='festival_grounds',
                                         main_present=['agnea', 'throne'], minor_present=[],
                                         last_winner=last_winner)
            return await agent.resolve(state, {}, [])

    result = asyncio.run(exercise())
    failures = [row for row in map(json.loads, (run / 'trace.jsonl').read_text().splitlines())
                if row['type'] == 'world_validation_failed']
    if error:
        assert len(requests) == 2 and error in requests[1]
        assert len(failures) == 1
        assert error in failures[0]['error']
        assert json.loads(failures[0]['raw_reply']) == first
    else:
        assert len(requests) == 1 and not failures
        if scene:
            outcome, _minor_moves = result
            assert outcome.content == content
        else:
            events, updated, _notes, _encounters = result
            assert events[0].content == content
            assert updated.characters['agnea'].where == first['state']['characters']['agnea']['where']
    assert state == load_state(world)


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


def _run_resolve(world, run, monkeypatch, state, choices, reply):
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', _fake_client(iter([json.dumps(reply)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.resolve(state, choices, [])

    return asyncio.run(exercise()), requests


def _run_round(world, run, monkeypatch, state, last_winner, reply):
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', _fake_client(iter([json.dumps(reply)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.round(state, [], place='festival_grounds',
                                     main_present=['agnea', 'throne'], minor_present=['Tam'],
                                     last_winner=last_winner)

    return asyncio.run(exercise()), requests


def test_world_of_accepted_for_own_attempt_part_of_day(tmp_path, monkeypatch):
    """A part_of_day outcome of = throne's own attempt may name her as subject."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor='world', of='throne', type='world',
                 content='Throné tracks Tam and observes him arguing.', perceived_by=['agnea'])
    reply = dict(call='part_of_day', events=[event], state=state.model_dump(exclude={'clock'}),
                situation_notes={s.id: 'Unchanged.' for s in state.situations})
    result, requests = _run_resolve(world, run, monkeypatch, state, {'throne': {}}, reply)
    events, _updated, _notes, _encounters = result
    assert len(requests) == 1
    assert events[0].content == 'Throné tracks Tam and observes him arguing.'
    assert events[0].of == 'throne'


def test_world_of_missing_rejected_by_subject_check(tmp_path, monkeypatch):
    """The same content without `of` fails M2, since throne is then just a subject."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor='world', type='world',
                 content='Throné tracks Tam and observes him arguing.', perceived_by=['agnea'])
    reply = dict(call='part_of_day', events=[event] * 2, state=state.model_dump(exclude={'clock'}),
                situation_notes={s.id: 'Unchanged.' for s in state.situations})
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient',
                        _fake_client(iter([json.dumps(reply), json.dumps(reply)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.resolve(state, {'throne': {}}, [])

    with pytest.raises(world_agent.SessionError, match='M2 subject check'):
        asyncio.run(exercise())


def test_world_of_other_main_character_in_content_rejected(tmp_path, monkeypatch):
    """An `of: throne` event still fails if some other main character is its subject."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor='world', of='throne', type='world',
                 content='Throné watches Tam leave. Agnea follows her.', perceived_by=['agnea'])
    reply = dict(call='part_of_day', events=[event] * 2, state=state.model_dump(exclude={'clock'}),
                situation_notes={s.id: 'Unchanged.' for s in state.situations})
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient',
                        _fake_client(iter([json.dumps(reply), json.dumps(reply)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.resolve(state, {'throne': {}}, [])

    with pytest.raises(world_agent.SessionError, match='M2 subject check'):
        asyncio.run(exercise())


def test_world_of_rejects_main_character_not_making_this_attempt(tmp_path, monkeypatch):
    """`of` naming a main character whose choice isn't part of this part_of_day call is rejected."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor='world', of='throne', type='world',
                 content='Throné tracks Tam and observes him arguing.', perceived_by=['agnea'])
    reply = dict(call='part_of_day', events=[event] * 2, state=state.model_dump(exclude={'clock'}),
                situation_notes={s.id: 'Unchanged.' for s in state.situations})
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient',
                        _fake_client(iter([json.dumps(reply), json.dumps(reply)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.resolve(state, {'agnea': {}}, [])

    with pytest.raises(world_agent.SessionError, match='World event of must name'):
        asyncio.run(exercise())


def test_world_of_scene_round_accepted_for_previous_winner(tmp_path, monkeypatch):
    """A scene_round outcome may set `of` to the previous round's winner, a main character."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor='world', of='throne', type='world',
                 content='Throné tracks Tam and finds him near the stalls.', perceived_by=['agnea'])
    reply = dict(call='scene_round', outcome=event, minor_moves={})
    result, requests = _run_round(world, run, monkeypatch, state,
                                  {'actor': 'throne', 'move': 'act'}, reply)
    outcome, _minor_moves = result
    assert len(requests) == 1
    assert outcome.of == 'throne'


def test_world_of_scene_round_rejects_non_winner(tmp_path, monkeypatch):
    """`of` naming a main character who was not the previous round's winner is rejected."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor='world', of='throne', type='world',
                 content='Throné tracks Tam and finds him near the stalls.', perceived_by=['agnea'])
    reply = dict(call='scene_round', outcome=event, minor_moves={})
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient',
                        _fake_client(iter([json.dumps(reply), json.dumps(reply)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.round(state, [], place='festival_grounds',
                                     main_present=['agnea', 'throne'], minor_present=['Tam'],
                                     last_winner={'actor': 'agnea', 'move': 'act'})

    with pytest.raises(world_agent.SessionError, match='World event of must name'):
        asyncio.run(exercise())
