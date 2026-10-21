import asyncio
import copy
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from story_engine.agents import character, world as world_agent
from story_engine.agents.sdk import SessionError
from story_engine.simulation import TickSession, run_tick
from story_engine.world.io import load_state, read_events, save_state

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('part,day,next_part', [('morning', 1, 'afternoon'), ('night', 2, 'morning')])
@pytest.mark.parametrize('bad_actor', [False, True])
def test_tick(tmp_path, monkeypatch, part, day, next_part, bad_actor):
    world = tmp_path / 'world'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run = tmp_path / 'run'
    run.mkdir()
    state = load_state(world)
    state.clock.part = part
    save_state(world, state)
    requests, clients = [], []
    reply = dict(call='part_of_day',
                 events=[dict(place='cropdale', actor='world', type='world',
                             content='The stalls open.', intent=None, perceived_by=list(state.characters))],
                 state=state.model_dump(exclude={'clock'}),
                 situation_notes={s.id: 'Preparations continue.' for s in state.situations})
    for char in reply['state']['characters'].values():
        char['where'] = 'cropdale'
    reply['state']['characters']['throne']['where'] = 'festival_grounds'
    invalid = copy.deepcopy(reply)
    invalid['events'][0]['actor'] = 'agnea'
    world_replies = iter([invalid, reply] if bad_actor else [reply])

    class FakeClient:
        def __init__(self, *, options):
            self.options = options
            self.is_world = options.system_prompt.startswith('# World')
            clients.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            requests.append((self.is_world, request))

        async def receive_response(self):
            data = next(world_replies) if self.is_world else dict(
                call='action', intent='Visit the stalls', move='act', urge=2,
                action='Heads to Cropdale.', say='Good morning!')
            yield ResultMessage('success', 1, 1, False, 1, 'fake',
                                usage={'input_tokens': 3}, result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', FakeClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', FakeClient)

    async def exercise():
        async with TickSession(world, run, root=ROOT) as session:
            return await run_tick(world, run, session=session)

    result = asyncio.run(exercise())
    assert load_state(world) == result
    assert (result.clock.day, result.clock.part) == (day, next_part)
    events = read_events(world)
    assert [event.actor for event in events] == ['agnea', 'throne', 'world']
    assert [event.id for event in events] == [1, 2, 3]
    assert all(event.part == part and event.day == 1 for event in events)
    for event in events[:2]:
        assert event.place == 'festival_grounds'
        assert event.perceived_by == ['agnea', 'throne']
        assert event.type == 'speech' and event.intent == 'Visit the stalls'
        assert event.content == 'Heads to Cropdale. Good morning!'
    assert len(clients) == 3
    character_requests = [json.loads(request) for is_world, request in requests if not is_world]
    assert all(request['perceived'] == [] and request['part'] == part for request in character_requests)
    if bad_actor:
        assert 'must not be a main character' in requests[-1][1]
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert trace[-1]['situation_notes'] == reply['situation_notes']
    assert len([row for row in trace if row['type'] == 'stage_usage']) == 3 + bad_actor

@pytest.mark.parametrize('failure,reason', [
    ('actor', 'must not be a main character'),
    ('intent', 'intent must be null'),
    ('place', "place must be in new state's places"),
    ('perceiver', 'only main characters'),
    ('characters', 'match world.json exactly'),
    ('notes', 'cover every situation'),
    ('clock', 'must omit clock'),
])
def test_world_final_validation_error(tmp_path, monkeypatch, failure, reason):
    world = tmp_path / 'world'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run = tmp_path / 'run'
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor='world', type='world',
                 content='The wind rises.', intent=None, perceived_by=['agnea'])
    reply = dict(call='part_of_day', events=[event], state=state.model_dump(exclude={'clock'}),
                 situation_notes={s.id: 'Unchanged.' for s in state.situations})
    if failure == 'actor':
        event['actor'] = 'agnea'
    elif failure == 'intent':
        event['intent'] = 'Secret'
    elif failure == 'place':
        event['place'] = 'missing'
    elif failure == 'perceiver':
        event['perceived_by'] = ['stranger']
    elif failure == 'characters':
        reply['state']['characters']['stranger'] = copy.deepcopy(reply['state']['characters']['agnea'])
    elif failure == 'notes':
        reply['situation_notes'] = {}
    else:
        reply['state']['clock'] = state.clock.model_dump()
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
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(reply))

    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', FakeClient)
    from story_engine.config import load_configs
    from story_engine.trace import TraceWriter
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            await agent.resolve(state, {}, [])

    with pytest.raises(SessionError, match=reason):
        asyncio.run(exercise())
    failures = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()
                if json.loads(line)['type'] == 'world_validation_failed']
    assert len(failures) == 2
    assert all(reason in row['error'] and json.loads(row['raw_reply']) == reply for row in failures)
    assert len(requests) == 2 and reason in requests[1]
    assert load_state(world) == state
    assert read_events(world) == []
