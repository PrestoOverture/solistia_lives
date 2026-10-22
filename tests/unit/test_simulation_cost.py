import asyncio
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from story_engine.agents import character, initializer, world as world_agent
from story_engine.config import load_configs
from story_engine.simulation import CostCapReached, TickSession, run_scene
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state
from story_engine.world.models import Event

ROOT = Path(__file__).resolve().parents[2]


def setup(tmp_path, monkeypatch, module, outputs):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    (run / 'scene_context.md').write_text('## Location\nCropdale')
    requests, closed = [], []
    replies = iter(outputs)

    class FakeClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.append(True)

        async def query(self, request):
            requests.append(request)

        async def receive_response(self):
            data, cost = next(replies)
            yield ResultMessage('success', 1, 1, False, 1, 'fake',
                                result=json.dumps(data), total_cost_usd=cost)

    monkeypatch.setattr(module, 'ClaudeSDKClient', FakeClient)
    return world, run, requests, closed


def rows(run):
    return list(map(json.loads, (run / 'trace.jsonl').read_text().splitlines()))


@pytest.mark.parametrize('kind', ['world', 'character', 'initializer'])
def test_cumulative_cost_and_world_event_delta(tmp_path, monkeypatch, kind):
    state = load_state(ROOT / 'tests/fixtures/worlds/agnea_throne')
    adjudicate = dict(call='adjudicate', verdicts={}, encounters=[])
    action = dict(call='action', intent='Wait', move='wait', urge=0, action='', say='')
    module = {'world': world_agent, 'character': character, 'initializer': initializer}[kind]
    valid = adjudicate if kind == 'world' else action
    outputs = [(valid, .10), (valid, .25)]
    if kind == 'initializer':
        outputs = [({}, .10), (state.model_dump(exclude={'clock'}), .25)]
        places = [tmp_path / 'cropdale.md', tmp_path / 'festival_grounds.md']
        for place in places:
            place.touch()
        monkeypatch.setattr(initializer.Path, 'rglob', lambda *args: iter(places))
        monkeypatch.setattr(initializer, 'record_api_host', lambda *args: None)
    world, run, requests, _ = setup(tmp_path, monkeypatch, module, outputs)
    models, settings = load_configs()
    event = Event(id=1, **state.clock.model_dump(), place='cropdale', actor='world',
                  type='world', content='The stalls open.', perceived_by=['agnea'])
    new = event.model_copy(update={'id': 2, 'content': 'The bell rings.'})

    async def exercise():
        if kind == 'initializer':
            await initializer.starting_state(ROOT, run, list(state.characters), 'cropdale',
                                            'Festival', models.initializer, settings.agent_max_turns,
                                            TraceWriter(run))
            return
        agent = (world_agent.WorldAgent(ROOT, run, world, models.world, settings.agent_max_turns, TraceWriter(run))
                 if kind == 'world' else character.CharacterAgent(ROOT, run, world, 'agnea', models.character,
                                                                  settings.agent_max_turns, TraceWriter(run)))
        async with agent:
            if kind == 'world':
                await agent.adjudicate(state, {}, [event.model_copy(update={"id": 99, "day": 0}), event])
                await agent.adjudicate(state, {}, [event, new])
            else:
                await agent.act([event])
                await agent.act([event, new])

    asyncio.run(exercise())
    usage = [row for row in rows(run) if row['type'] == 'stage_usage']
    assert [row['total_cost_usd'] for row in usage] == [.10, .25]
    assert [row['call_cost_usd'] for row in usage] == pytest.approx([.10, .15])
    if kind == 'world':
        assert json.loads(requests[0])['events'] == [event.model_dump()]
        assert json.loads(requests[1])['events'] == [new.model_dump()]


@pytest.mark.parametrize('payer', ['character', 'world'])
def test_scene_cost_cap_stops_immediately(tmp_path, monkeypatch, payer):
    action = dict(call='action', intent='Wait', move='wait', urge=0, action='', say='')
    world, run, requests, closed = setup(tmp_path, monkeypatch, character,
                                        [(action, .10), (action, .15)])
    state = load_state(world)
    resolution = dict(call='scene_round', outcome=None, minor_moves={})
    if payer == 'world':
        # Character calls total exactly the cap; the World call crosses it.
        class WorldClient:
            def __init__(self, *, options): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): closed.append(True)
            async def query(self, request): requests.append(request)
            async def receive_response(self):
                yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(resolution), total_cost_usd=.01)
        monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)
    else:
        monkeypatch.setattr(world_agent, 'ClaudeSDKClient', character.ClaudeSDKClient)

    async def exercise():
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.max_cost_usd = .2 if payer == 'character' else .25
            with pytest.raises(CostCapReached):
                await run_scene(world, session, state, 'festival_grounds', list(state.characters), [])
            assert session.spend_usd == pytest.approx(.25 if payer == 'character' else .26)

    asyncio.run(exercise())
    assert len(requests) == (2 if payer == 'character' else 3)
    assert len(closed) == 4
    assert rows(run)[-1]['type'] == 'cost_cap_reached'
    assert rows(run)[-1]['spend_usd'] == pytest.approx(.25 if payer == 'character' else .26)
