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


@pytest.mark.parametrize('case,scene,choices,content,error', [
    ('locked', True, {'throne': {'move': 'leave'}}, 'The wind rises.', 'M1'),
    ('missing_move', True, {}, 'The wind rises.', 'M1'),
    ('tick', False, {}, 'The wind rises.', None),
    ('leave', True, {'agnea': {'move': 'leave'}}, 'The wind rises.', None),
    ('subject', True, {}, 'Throné rises.', 'Throné rises.'),
    ('subject', True, {}, "throne's hands move.", "throne's hands move."),
    ('subject', True, {}, 'Agnea nods.', 'Agnea nods.'),
    ('subject', True, {}, 'The Dancer smiles.', 'The Dancer smiles.'),
    ('subject', True, {}, 'The wind rises. Throné’s hands move.', 'Throné’s hands move.'),
    ('quoted', True, {}, '"Agnea! Over here," the boy calls.', None),
    ('quoted', True, {}, '“Agnea! Over here,” the boy calls.', None),
    ('subject', True, {}, '"Hello," Agnea nods.', 'Agnea nods.'),
    ('object', True, {}, 'Gus hands Agnea a basket.', None),
])
@pytest.mark.parametrize('actor', ['world', 'Gus'])
def test_world_d2_validation(tmp_path, monkeypatch, case, scene, choices, content, error, actor):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    good = dict(events=[dict(place='festival_grounds', actor=actor, type='world',
                             content='Gus hands Agnea a basket.', perceived_by=['agnea'])],
                state=state.model_dump(exclude={'clock'}),
                situation_notes={s.id: 'Unchanged.' for s in state.situations})
    first = copy.deepcopy(good)
    first['events'][0]['content'] = content
    if case in ('locked', 'missing_move', 'tick', 'leave'):
        first['state']['characters']['agnea']['where'] = 'cropdale'
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
            return await agent.resolve(state, choices, [], scene_round=scene)

    events, updated, _ = asyncio.run(exercise())
    failures = [row for row in map(json.loads, (run / 'trace.jsonl').read_text().splitlines())
                if row['type'] == 'world_validation_failed']
    if error:
        assert len(requests) == 2 and error in requests[1]
        assert len(failures) == 1
        assert error in failures[0]['error']
        assert json.loads(failures[0]['raw_reply']) == first
        if case == 'subject':
            assert 'event index 0' in requests[1]
    else:
        assert len(requests) == 1 and not failures
        assert events[0].content == content
        assert updated.characters['agnea'].where == first['state']['characters']['agnea']['where']
    assert state == load_state(world)
