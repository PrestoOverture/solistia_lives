"""Fixed session schemas and call-dependent validation through fake SDK clients."""
import asyncio
import copy
import json
import shutil
from pathlib import Path

import pytest

from story_engine.agents import character, world as world_agent
from story_engine.agents.sdk import SessionError, json_schema_output, require_person_sex
from story_engine.config import Role, load_configs
from story_engine.stages import catalog_schema
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state
from test_structured_output import _record_clients
from world_replies import day_start_reply

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def workspace(tmp_path):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    return world, run


def make_agent(workspace, cls):
    world, run = workspace
    models, settings = load_configs()
    role = (models.character if cls is character.CharacterAgent else models.world).model_copy(
        update={'schema_mode': 'session'})
    args = (ROOT, run, world)
    if cls is character.CharacterAgent:
        args += ('throne',)
    return cls(*args, role, settings.agent_max_turns, TraceWriter(run))


def test_world_fixed_schema(workspace, monkeypatch):
    state = load_state(workspace[0])
    empty = state.model_copy(deep=True)
    empty.characters['throne'].where = 'cropdale'
    opening = day_start_reply(situations=[
        state.situations[0].model_dump() | {'id': 'new-day', 'heard': 'An invitation arrives.'}])
    replies = [opening, {'call': 'adjudicate'}, {'call': 'adjudicate'},
               {'call': 'adjudicate'}, {'call': 'scene_round'},
               {'call': 'scene_round', 'resolution': 'none'},
               {'call': 'scene_round', 'resolution': 'none'}]
    clients = _record_clients(monkeypatch, world_agent, replies)
    agent = make_agent(workspace, world_agent.WorldAgent)
    expected = catalog_schema(require_person_sex(json_schema_output(world_agent.WorldReply)), agent.catalogs)
    async def exercise():
        async with agent:
            await agent.day_start(state, [])
            await agent.adjudicate(state, {}, [])
            await agent.adjudicate(empty, {'throne': {'kind': 'attempt'}}, [])
            for winner, closing in [(None, False), ({'id': 42, 'actor': 'throne'}, False),
                                    ({'id': 42, 'actor': 'throne'}, True)]:
                await agent.round(state, [], place='cropdale', main_present=['throne'],
                                  minor_present=[], last_winner=winner, scene='1',
                                  round_number=2, closing=closing)
    asyncio.run(exercise())
    assert len(clients) == 6
    assert all(c.options.output_format == expected for c in clients)
    assert all(c.options.output_format is agent.session_output for c in clients)


def test_character_fixed_schema(workspace, monkeypatch):
    replies = [{'call': 'day_start', 'goals': ['Find quiet']},
               {'call': 'plan', 'kind': 'attempt', 'intent': 'Rest', 'aim': 'Find quiet'},
               {'call': 'action', 'intent': 'Rest', 'move': 'wait', 'urge': 0, 'action': '', 'say': ''},
               {'call': 'end_of_day', 'summary': 'I rested.'}]
    clients = _record_clients(monkeypatch, character, replies)
    agent = make_agent(workspace, character.CharacterAgent)
    expected = catalog_schema(json_schema_output(character.CharacterReply), agent.catalogs)
    async def exercise():
        async with agent:
            await agent.day_start()
            await agent.choose('morning', [])
            await agent.act([])
            await agent.summarize([])
    asyncio.run(exercise())
    assert len(clients) == 4
    assert all(c.options.output_format == expected for c in clients)


def test_offscreen_fixed_schema(workspace, monkeypatch):
    replies = [{'call': 'offscreen', 'situation_notes': notes}
               for notes in ({'one': 'Unchanged.'}, {'two': 'Unchanged.'}, {})]
    clients = _record_clients(monkeypatch, world_agent, replies)
    agent = make_agent(workspace, world_agent.OffscreenAgent)
    before = copy.deepcopy(agent.session_output)
    async def exercise():
        async with agent:
            for ids in ({'one'}, {'two'}, set()):
                await agent.offscreen(load_state(workspace[0]), ids)
    asyncio.run(exercise())
    assert len(clients) == 3
    assert all(c.options.output_format == before for c in clients)
    assert before == catalog_schema(require_person_sex(json_schema_output(world_agent.OffscreenReply)),
                                    agent.catalogs)


@pytest.mark.parametrize('case,error', [
    ('wrong_world', 'call'), ('wrong_character', 'call'), ('wrong_offscreen', 'call'),
    ('introduce', 'Introduce a new person'), ('resolution', 'resolution'),
    ('outcome', 'non-empty outcome'), ('notes_missing', 'situation_notes'),
    ('notes_extra', 'situation_notes'),
])
def test_session_validation_retries_then_existing_failure(workspace, monkeypatch, case, error):
    state = load_state(workspace[0])
    cls = (character.CharacterAgent if case == 'wrong_character' else
           world_agent.OffscreenAgent if case in {'wrong_offscreen', 'notes_missing', 'notes_extra'}
           else world_agent.WorldAgent)
    bad = {
        'wrong_world': {'call': 'scene_round'},
        'wrong_character': {'call': 'end_of_day', 'summary': 'Rested.'},
        'wrong_offscreen': {'call': 'adjudicate'},
        'introduce': {'call': 'adjudicate'},
        'resolution': {'call': 'scene_round'},
        'outcome': {'call': 'scene_round', 'resolution': 'succeeded'},
        'notes_missing': {'call': 'offscreen', 'situation_notes': {}},
        'notes_extra': {'call': 'offscreen', 'situation_notes': {'one': 'Same.', 'extra': 'Same.'}},
    }[case]
    requests = []
    from claude_agent_sdk import ResultMessage
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
            yield ResultMessage('success', 1, 1, False, 1, 'fake', structured_output={'reply': bad})
    monkeypatch.setattr(character if cls is character.CharacterAgent else world_agent,
                        'ClaudeSDKClient', Client)
    agent = make_agent(workspace, cls)
    async def exercise():
        async with agent:
            if cls is character.CharacterAgent:
                return await agent.choose('morning', [])
            if cls is world_agent.OffscreenAgent:
                return await agent.offscreen(state, {'one'})
            if case in {'resolution', 'outcome'}:
                return await agent.round(state, [], place='cropdale', main_present=['throne'],
                                         minor_present=[], last_winner={'id': 42, 'actor': 'throne'},
                                         scene='1', round_number=2)
            state.characters['throne'].where = 'cropdale'
            return await agent.adjudicate(state, {'throne': {'kind': 'attempt'}}, [])
    if case == 'introduce':
        event, encounters, updated = asyncio.run(exercise())
        assert not event.ops and not encounters and updated == state
        assert 'empty_spot_unfilled' in (workspace[1] / 'trace.jsonl').read_text()
    elif cls is world_agent.OffscreenAgent:
        assert asyncio.run(exercise()) == ([], state, {})
        assert 'offscreen_dropped' in (workspace[1] / 'trace.jsonl').read_text()
    else:
        with pytest.raises(SessionError):
            asyncio.run(exercise())
    assert len(requests) == 2
    assert error in requests[1]


def test_schema_config_defaults():
    role = Role(model='fake', effort=None, thinking=None)
    assert role.schema_mode == 'call'
    models, _ = load_configs()
    spark, _ = load_configs('config/models_spark.yaml')
    assert models.world.schema_mode == models.character.schema_mode == 'session'
    assert spark.world.schema_mode == spark.character.schema_mode == 'call'


def test_session_round_without_winner_accepts_null_resolution(workspace, monkeypatch):
    state = load_state(workspace[0])
    from claude_agent_sdk import ResultMessage
    class Client:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def query(self, request):
            pass
        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake', structured_output={'reply': {
                'call': 'scene_round', 'resolution': None, 'outcome': None, 'ops': [], 'minor_moves': {}}})
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', Client)
    agent = make_agent(workspace, world_agent.WorldAgent)
    async def exercise():
        async with agent:
            return await agent.round(state, [], place='cropdale', main_present=['throne'],
                                     minor_present=[], last_winner=None, scene='1', round_number=2)
    asyncio.run(exercise())
    assert 'world_validation_failed' not in (workspace[1] / 'trace.jsonl').read_text()
