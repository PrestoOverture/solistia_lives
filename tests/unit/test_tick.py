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
    adjudicate_reply = dict(call='adjudicate', verdicts={
        'agnea': dict(status='settled', outcome='Agnea heads into Cropdale.', where='cropdale', spot=None),
        'throne': dict(status='settled', outcome='Throné stays at the festival grounds.',
                      where='festival_grounds', spot=None),
    }, encounters=[])
    offscreen_reply = dict(
        call='offscreen',
        events=[dict(place='cropdale', actor='world', type='world', content='The stalls open.', intent=None)],
        people={}, situations=[s.model_dump() for s in state.situations],
        places=[p.model_dump() for p in state.places],
        situation_notes={s.id: 'Preparations continue.' for s in state.situations})
    invalid_offscreen = copy.deepcopy(offscreen_reply)
    invalid_offscreen['events'][0]['actor'] = 'agnea'
    world_replies = iter([adjudicate_reply] +
                        ([invalid_offscreen, offscreen_reply] if bad_actor else [offscreen_reply]))

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
                call='plan', intent='Visit the stalls', where='cropdale', spot=None,
                aim='Heads to the stalls.')
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
    assert [event.actor for event in events] == ['agnea', 'throne', 'world', 'world', 'world']
    assert [event.id for event in events] == [1, 2, 3, 4, 5]
    assert all(event.part == part and event.day == 1 for event in events)
    for event in events[:2]:
        assert event.place == 'festival_grounds'
        assert event.perceived_by == [event.actor]
        assert event.type == 'plan' and event.intent == 'Visit the stalls'
        assert event.content == 'Heads to the stalls.'
    outcomes = {event.of: event for event in events if event.of}
    assert outcomes['agnea'].content == 'Agnea heads into Cropdale.' and outcomes['agnea'].place == 'cropdale'
    assert (outcomes['throne'].content == 'Throné stays at the festival grounds.'
            and outcomes['throne'].place == 'festival_grounds')
    offscreen_event = events[-1]
    assert offscreen_event.of is None
    assert offscreen_event.content == 'The stalls open.' and offscreen_event.place == 'cropdale'
    assert offscreen_event.perceived_by == ['agnea']  # only agnea ended up at cropdale
    assert len(clients) == 3
    character_requests = [json.loads(request) for is_world, request in requests if not is_world]
    assert all(request['perceived'] == [] and request['part'] == part for request in character_requests)
    if bad_actor:
        assert 'must not be a main character' in requests[-1][1]
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert trace[-1]['situation_notes'] == offscreen_reply['situation_notes']
    assert len([row for row in trace if row['type'] == 'stage_usage']) == 4 + bad_actor


@pytest.mark.parametrize('failure,reason', [
    ('actor', 'must not be a main character'),
    ('intent', 'intent must be null'),
    ('place', 'place must be in places'),
    ('notes', 'cover every situation'),
])
def test_offscreen_validation_error(tmp_path, monkeypatch, failure, reason):
    """Off-screen events are checked the same way as before: actor, intent, place
    references, and situation_notes coverage (D27, D28)."""
    world = tmp_path / 'world'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run = tmp_path / 'run'
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor='world', type='world',
                 content='The wind rises.', intent=None)
    reply = dict(call='offscreen', events=[event],
                people={}, situations=[s.model_dump() for s in state.situations],
                places=[p.model_dump() for p in state.places],
                situation_notes={s.id: 'Unchanged.' for s in state.situations})
    if failure == 'actor':
        event['actor'] = 'agnea'
    elif failure == 'intent':
        event['intent'] = 'Secret'
    elif failure == 'place':
        event['place'] = 'missing'
    else:
        reply['situation_notes'] = {}
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
            await agent.offscreen(state, [], {s.id for s in state.situations if s.status == 'open'})

    with pytest.raises(SessionError, match=reason):
        asyncio.run(exercise())
    failures = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()
                if json.loads(line)['type'] == 'world_validation_failed']
    assert len(failures) == 2
    assert all(reason in row['error'] and json.loads(row['raw_reply']) == reply for row in failures)
    assert len(requests) == 2 and reason in requests[1]
    assert load_state(world) == state
    assert read_events(world) == []
