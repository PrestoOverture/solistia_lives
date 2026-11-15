"""Situation links are metadata, validated without another model call."""
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
        metadata = {} if valid is None else {'about': about}
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
