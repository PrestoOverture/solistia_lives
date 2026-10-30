import asyncio
import json
import shutil
from pathlib import Path

import jsonschema
import pytest
from claude_agent_sdk import ResultMessage
from typer.testing import CliRunner

from story_engine.agents import initializer, world as world_agent
from story_engine.cli import app
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world import sex
from story_engine.world.io import load_state
from story_engine.world.models import Person, WorldState
from story_engine.world.ops import Introduce

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def world(tmp_path, monkeypatch):
    target = tmp_path / 'worlds/fixture'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', target)
    shutil.copytree(ROOT / 'config', tmp_path / 'config')
    genesis = json.loads((target / 'genesis.json').read_text())
    genesis['people'] = {
        'Gus': dict(where='cropdale', wants=['Serve supper'], commitments=[]),
        'Known': dict(where='cropdale', wants=['Rest'], commitments=[], sex='f'),
    }
    (target / 'genesis.json').write_text(json.dumps(genesis))
    event = dict(id=1, day=1, part='morning', place='cropdale', actor='world',
                 type='world', content='Opaque content.', perceived_by=[],
                 ops=[dict(op='introduce', name='Visitor', where='cropdale',
                           wants=['Find work'], commitments=[]),
                      dict(op='wants', person='Gus', wants=['Clean up'])])
    (target / 'events.jsonl').write_text(json.dumps(event) + '\n')
    (target / 'state.json').write_text(load_state(target).model_dump_json())
    card = tmp_path / 'kb/characters/gus.md'
    card.parent.mkdir(parents=True)
    card.write_text('---\nname: gus\naliases: [Gus]\n---\n# Gus\nA tavern keeper.')
    monkeypatch.chdir(tmp_path)
    return target


def fake_model(monkeypatch, reply):
    calls = []

    class FakeClient:
        def __init__(self, *, options):
            self.options = options
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def query(self, request):
            calls.append((self.options, json.loads(request)))
        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake', structured_output=reply)

    monkeypatch.setattr(sex, 'ClaudeSDKClient', FakeClient)
    return calls


def test_backfill_preserves_artifacts_and_rerun_skips_model(world, monkeypatch):
    calls = fake_model(monkeypatch, {'people': {'Gus': 'm', 'Visitor': 'f'}})
    before = {name: json.loads((world / name).read_text()) for name in ['genesis.json', 'events.jsonl']}
    result = CliRunner().invoke(app, ['world', 'backfill-sex', 'fixture', '--models', 'config/models.yaml'])
    assert result.exit_code == 0, result.output
    assert 'Updated 2 people; skipped 1' in result.output
    assert len(calls) == 1
    options, request = calls[0]
    assert options.model == load_configs()[0].world.model
    assert request['people'] == [
        dict(name='Gus', wants=['Clean up'], kb_cards=[Path('kb/characters/gus.md').read_text()]),
        dict(name='Visitor', wants=['Find work'], kb_cards=[]),
    ]
    jsonschema.validate({'people': {'Gus': 'm', 'Visitor': 'f'}}, options.output_format['schema'])
    genesis = json.loads((world / 'genesis.json').read_text())
    event = json.loads((world / 'events.jsonl').read_text())
    assert genesis['people']['Gus'].pop('sex') == 'm'
    assert event['ops'][0].pop('sex') == 'f'
    assert genesis == before['genesis.json']
    assert event == before['events.jsonl']
    state = load_state(world)
    assert {name: p.sex for name, p in state.people.items()} == {'Gus': 'm', 'Known': 'f', 'Visitor': 'f'}
    assert state == WorldState.model_validate_json((world / 'state.json').read_bytes())
    after = {p: p.read_bytes() for p in world.iterdir() if p.is_file()}
    def unexpected(**kwargs):
        pytest.fail('Rerun must not open a model session')
    monkeypatch.setattr(sex, 'ClaudeSDKClient', unexpected)
    result = CliRunner().invoke(app, ['world', 'backfill-sex', 'fixture'])
    assert result.exit_code == 0, result.output
    assert 'Updated 0 people; skipped 3' in result.output
    assert {p: p.read_bytes() for p in after} == after


@pytest.mark.parametrize('people', [{'Gus': 'm'}, {'Gus': 'm', 'Visitor': 'f', 'extra': 'm'},
                                    {'Gus': 'other', 'Visitor': 'f'}])
def test_invalid_reply_writes_no_world_artifacts(world, monkeypatch, people):
    fake_model(monkeypatch, {'people': people})
    before = {p: p.read_bytes() for p in world.iterdir() if p.is_file()}
    result = CliRunner().invoke(app, ['world', 'backfill-sex', 'fixture'])
    assert result.exit_code == 1
    assert {p: p.read_bytes() for p in before} == before


@pytest.mark.parametrize('agent', ['world', 'initializer'])
def test_actual_sdk_creation_schemas_require_sex(tmp_path, monkeypatch, agent):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'scene_context.md').write_text('## Context\nA festival.')
    schemas = []
    class Captured(Exception):
        pass
    class CaptureClient:
        def __init__(self, *, options):
            schemas.append(options.output_format['schema'])
            raise Captured
    module = world_agent if agent == 'world' else initializer
    monkeypatch.setattr(module, 'ClaudeSDKClient', CaptureClient)
    monkeypatch.setattr(initializer, 'record_api_host', lambda *args: None)
    models, settings = load_configs(ROOT / 'config/models.yaml')
    async def capture():
        if agent == 'world':
            async with world_agent.WorldAgent(ROOT, run, run, models.world,
                                              settings.agent_max_turns, TraceWriter(run)):
                pass
        else:
            await initializer.starting_state(ROOT, run, ['agnea', 'throne'], 'cropdale',
                                             'A festival', models.initializer,
                                             settings.agent_max_turns, TraceWriter(run))
    with pytest.raises(Captured):
        asyncio.run(capture())
    schema = schemas[0]
    person = dict(where='cropdale', wants=['Rest'], commitments=[], sex='m')
    if agent == 'world':
        output = {'reply': dict(call='adjudicate', ops=[dict(op='introduce', name='Gus', **person)])}
        field = output['reply']['ops'][0]
    else:
        output = dict(places=[dict(slug='cropdale', details=[])], situations=[],
                      characters={name: dict(where='cropdale', goals=['Rest'], commitments=[])
                                  for name in ['agnea', 'throne']}, people={'Gus': person})
        field = output['people']['Gus']
    jsonschema.validate(output, schema)
    for invalid in [None, 'unknown']:
        field['sex'] = invalid
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(output, schema)
    del field['sex']
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(output, schema)
    # The disk schemas remain backward compatible.
    assert Person.model_validate(dict(where='cropdale', wants=['Rest'], commitments=[])).sex is None
    assert Introduce(name='Gus', where='cropdale', wants=['Rest']).sex is None
