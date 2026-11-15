"""Situation links are metadata, validated without inspecting prose."""
import asyncio
import json
import re
import shutil
from pathlib import Path

import pytest

from story_engine.agents.world import WorldAgent, OffscreenAgent
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.models import Event
from story_engine.world.io import commit_event, load_state, read_events
from test_day_start import fake_sdk

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('mode', ['call', 'session'])
@pytest.mark.parametrize('kind', ['scene_round', 'offscreen'])
@pytest.mark.parametrize('valid', [True, False, None])
def test_about_saved_or_cleared_without_retry(tmp_path, monkeypatch, mode, kind, valid):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    if kind == 'scene_round':
        commit_event(world, Event(id=0, **state.clock.model_dump(), place='festival_grounds',
                     actor='agnea', type='action', content='Tries the gate.', move='act',
                     perceived_by=['agnea'], scene='1', round=1, about=state.situations[0].id))
    situation_id = state.situations[0].id
    about = situation_id if valid else 'unknown'

    def respond(client, request):
        schema = client.options.output_format['schema']
        if mode == 'call':
            definition = schema if kind == 'scene_round' else schema['$defs']['OffscreenEvent']
            assert 'about' in definition['required']
            prop = definition['properties']['about']
            assert prop['enum'] == [*[s.id for s in state.situations], None]
        else:
            definition = schema['$defs']['RoundResolution' if kind == 'scene_round' else 'OffscreenEvent']
            assert 'about' not in definition.get('required', [])
            assert definition['properties']['about']['anyOf'] == [{'type': 'string'}, {'type': 'null'}]
        metadata = {'about': None if valid is None else about}
        if mode == 'call' and valid is None:
            metadata = {}  # Per-call mode keeps its existing missing-key behavior.
        if kind == 'scene_round':
            assert all('about' not in e for e in request['events'])
            return dict(call=kind, resolution='succeeded', odds='certain', outcome='The gate opens.', **metadata)
        return dict(call=kind, events=[dict(place='festival_grounds', content='News arrives.', **metadata)],
                    situation_notes={s.id: 'Unchanged.' for s in state.situations})

    clients = fake_sdk(monkeypatch, respond)
    models, settings = load_configs()
    models.world.schema_mode = mode

    async def exercise():
        cls = WorldAgent if kind == 'scene_round' else OffscreenAgent
        async with cls(ROOT, run, world, models.world, settings.agent_max_turns, TraceWriter(run)) as agent:
            if kind == 'scene_round':
                event, _, _ = await agent.round(state, read_events(world), place='festival_grounds', main_present=['agnea'],
                    minor_present=[], last_winner=dict(id=1, actor='agnea'), scene='1', round_number=2)
            else:
                events, _, _ = await agent.offscreen(state, {s.id for s in state.situations})
                event, = events
            commit_event(world, event)
    asyncio.run(exercise())
    saved = read_events(world)[-1]
    assert saved.about == (situation_id if valid else None)
    assert 'about' not in saved.agent_view()
    assert json.loads((world / 'events.jsonl').read_text().splitlines()[-1])['about'] == saved.about
    assert sum(len(c.calls) for c in clients) == 1
    traces = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert sum(t.get('type') == 'about_cleared' for t in traces) == int(valid is False)


@pytest.mark.parametrize('kind', ['scene_round', 'offscreen'])
@pytest.mark.parametrize('case', ['corrected', 'missing', 'null'])
def test_session_about_presence(tmp_path, monkeypatch, kind, case):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    situation_id = state.situations[0].id
    if kind == 'scene_round':
        commit_event(world, Event(id=0, **state.clock.model_dump(), place='festival_grounds',
                     actor='agnea', type='action', content='Tries the gate.', move='act',
                     perceived_by=['agnea'], scene='1', round=1))

    def respond(client, request):
        metadata = {}
        if case == 'null':
            metadata['about'] = None
        elif case == 'corrected' and len(client.calls) > 1:
            metadata['about'] = situation_id
        if len(client.calls) > 1:
            assert isinstance(request, str)
            assert 'about' in request
        if kind == 'scene_round':
            return dict(call=kind, resolution='succeeded', odds='certain',
                        outcome='The gate opens.', **metadata)
        # A valid first event must not hide a missing key on a later event.
        return dict(call=kind, events=[
            dict(place='festival_grounds', content='The market opens.', about=None),
            dict(place='festival_grounds', content='News arrives.', **metadata)],
            situation_notes={s.id: 'Unchanged.' for s in state.situations})

    clients = fake_sdk(monkeypatch, respond)
    models, settings = load_configs()
    models.world.schema_mode = 'session'
    models.world.retries = 1

    async def exercise():
        cls = WorldAgent if kind == 'scene_round' else OffscreenAgent
        async with cls(ROOT, run, world, models.world, settings.agent_max_turns, TraceWriter(run)) as agent:
            if kind == 'scene_round':
                event, _, _ = await agent.round(state, read_events(world), place='festival_grounds',
                    main_present=['agnea'], minor_present=[], last_winner=dict(id=1, actor='agnea'),
                    scene='1', round_number=2)
                commit_event(world, event)
            else:
                events, _, _ = await agent.offscreen(state, {s.id for s in state.situations})
                assert len(events) == 2
                for event in events:
                    commit_event(world, event)
    asyncio.run(exercise())

    assert read_events(world)[-1].about == (situation_id if case == 'corrected' else None)
    assert sum(len(c.calls) for c in clients) == (1 if case == 'null' else 2)
    traces = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    missing = [t for t in traces if t['type'] == 'about_missing']
    assert len(missing) == int(case == 'missing')
    if missing:
        assert missing[0]['call'] == kind
        assert missing[0]['turn'] == 1
    failures = [t for t in traces if t['type'] == 'world_validation_failed']
    assert len(failures) == int(case != 'null')


def test_legacy_event_loads(tmp_path):
    world = tmp_path / 'world'
    world.mkdir()
    row = dict(id=1, day=1, part='morning', place='cropdale', actor='world', type='world',
               content='News arrives.', perceived_by=[])
    (world / 'events.jsonl').write_text(json.dumps(row) + '\n')
    event, = read_events(world)
    assert event.about is None


def test_prompt_examples_include_resolution_metadata():
    world = (ROOT / 'prompts/world.md').read_text().split('## scene_round', 1)[1]
    examples = [json.loads(block) for block in re.findall(r'```(?:json)?\n(.*?)\n```', world, re.S)]
    no_winner, winner = examples
    assert no_winner['resolution'] is None
    assert no_winner['outcome'] is None
    assert winner['resolution'] == 'succeeded'
    assert winner['outcome']
    assert 'about' in winner
    assert winner['odds'] in {'likely', 'even', 'unlikely'}
    assert winner['failure']['outcome']
    assert 'ops' in winner['failure']

    offscreen = (ROOT / 'prompts/world_offscreen.md').read_text()
    example = json.loads(re.search(r'```(?:json)?\n(.*?)\n```', offscreen, re.S)[1])
    assert example['events']
    assert all('about' in event for event in example['events'])
