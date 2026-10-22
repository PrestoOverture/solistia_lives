import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from typer.testing import CliRunner

from story_engine.agents import curator, narrator
from story_engine.cli import app
from story_engine.runs import RunMeta
from story_engine.world.io import append_event, append_scene, load_state, save_state
from story_engine.world.models import Event, SceneRecord

ROOT = Path(__file__).resolve().parents[2]
EPISODE = dict(scenes=['A', 'B'], pov='agnea', why='A choice resolved.')
DRAFT = "# A Festival Evening\n\nAgnea laughed.\n"


@pytest.fixture
def world(tmp_path, monkeypatch):
    for name in ('config', 'prompts', 'cards'):
        shutil.copytree(ROOT / name, tmp_path / name)
    world = tmp_path / 'worlds/test'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    append_event(world, Event(id=1, day=1, part='morning', place='cropdale', scene='A',
                             actor='agnea', type='action', content='Agnea waves.',
                             intent='Greet', perceived_by=['agnea', 'throne']))
    append_event(world, Event(id=2, day=1, part='morning', place='cropdale', scene='A',
                             actor='throne', type='speech', content='Throné answers.',
                             intent='Chat', perceived_by=['agnea', 'throne']))
    append_event(world, Event(id=3, day=1, part='afternoon', place='cropdale',
                             actor='world', type='world', content='The bell rings.',
                             perceived_by=['agnea', 'throne']))
    append_event(world, Event(id=4, day=1, part='evening', place='cropdale', scene='B',
                             actor='agnea', type='action', content='Agnea resolves it.',
                             intent='Resolve', perceived_by=['agnea', 'throne']))
    append_event(world, Event(id=5, day=1, part='night', place='cropdale', scene='C',
                             actor='throne', type='speech', content='An unrelated scene.',
                             intent='Elsewhere', perceived_by=['throne']))
    append_scene(world, SceneRecord(id='A', day=1, part='morning', place='cropdale',
                                    participants=['agnea', 'throne'], first_event_id=1, last_event_id=2,
                                    rounds=2, end='one_left'))
    append_scene(world, SceneRecord(id='B', day=1, part='evening', place='cropdale',
                                    participants=['agnea'], first_event_id=4, last_event_id=4,
                                    rounds=1, end='one_left'))
    append_scene(world, SceneRecord(id='C', day=1, part='night', place='cropdale',
                                    participants=['throne'], first_event_id=5, last_event_id=5,
                                    rounds=1, end='one_left'))
    state = load_state(world)
    state.clock.day = 2
    save_state(world, state)
    monkeypatch.chdir(tmp_path)
    return world


def fake_curator(monkeypatch, replies):
    replies = iter(replies)

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
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=next(replies), total_cost_usd=0.1)

    monkeypatch.setattr(curator, 'ClaudeSDKClient', Client)


def fake_narrator(monkeypatch, draft=DRAFT):
    calls, options, lifecycle = [], [], []

    class Client:
        def __init__(self, **kwargs):
            options.append(kwargs['options'])

        async def __aenter__(self):
            lifecycle.append('enter')
            return self

        async def __aexit__(self, *args):
            lifecycle.append('exit')

        async def query(self, request):
            calls.append(request)

        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=draft, total_cost_usd=0.2)

    monkeypatch.setattr(narrator, 'ClaudeSDKClient', Client)
    return calls, options, lifecycle


def test_narrator_request_scopes_events_and_intents(world, monkeypatch):
    fake_curator(monkeypatch, [json.dumps(EPISODE)])
    calls, options, lifecycle = fake_narrator(monkeypatch)
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert lifecycle == ['enter', 'exit']
    assert options[0].tools == options[0].allowed_tools == ['Read']
    request = json.loads(calls[0])
    assert request['pov'] == 'agnea'
    events = request['events']
    assert [event['id'] for event in events] == [1, 2, 3, 4]
    assert [event['intent'] for event in events] == ['Greet', None, None, 'Resolve']
    assert (run / 'draft.md').read_text() == DRAFT
    assert (run / 'story.md').read_bytes() == (run / 'draft.md').read_bytes()
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'passed'


def test_act_request_scopes_scene_and_transition_events(world, monkeypatch):
    calls, options, lifecycle = fake_narrator(monkeypatch, draft='# Agnea resolves it.\n\nShe smiled.\n')
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'B', '--pov', 'agnea'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert lifecycle == ['enter', 'exit']
    assert options[0].tools == options[0].allowed_tools == ['Read']
    request = json.loads(calls[0])
    assert request['pov'] == 'agnea'
    assert [event['id'] for event in request['scene_events']] == [4]
    assert [event['intent'] for event in request['scene_events']] == ['Resolve']
    assert [event['id'] for event in request['part_of_day_events']] == [3]
    assert [event['intent'] for event in request['part_of_day_events']] == [None]
    assert request['previous_acts'] == []
    assert (run / 'acts/act_1.md').read_text() == '# Agnea resolves it.\n\nShe smiled.\n'
    assert not (run / 'draft.md').exists()
    assert not (run / 'episode.json').exists()
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'passed' and meta.day == 1


def test_act_only_pov_events_carry_intent(world, monkeypatch):
    calls, _, _ = fake_narrator(monkeypatch)
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'A', '--pov', 'agnea'])
    assert result.exit_code == 0, result.output
    request = json.loads(calls[0])
    events = request['scene_events']
    assert [event['id'] for event in events] == [1, 2]
    assert [event['intent'] for event in events] == ['Greet', None]


@pytest.mark.parametrize('args,message', [
    (['--act', 'Z', '--pov', 'agnea'], 'no such scene'),
    (['--act', 'B', '--pov', 'throne'], 'not a participant'),
    (['--act', 'A'], 'given together'),
    (['--pov', 'agnea'], 'given together'),
])
def test_act_validation_errors_exit_1(world, monkeypatch, args, message):
    calls, _, _ = fake_narrator(monkeypatch)
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1', *args])
    assert result.exit_code == 1
    assert message in result.output
    assert not calls


def test_episode_from_skips_curator(world, monkeypatch):
    class UnexpectedCurator:
        def __init__(self, **kwargs):
            pytest.fail('world tell --episode-from must not call the curator')

    fake_curator(monkeypatch, [json.dumps(EPISODE)])
    source = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1', '--stop-after', 'curate'])
    assert source.exit_code == 0, source.output
    source_run = Path(source.output.strip())

    monkeypatch.setattr(curator, 'ClaudeSDKClient', UnexpectedCurator)
    calls, _, _ = fake_narrator(monkeypatch)
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--episode-from', source_run.name])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert run != source_run
    assert calls  # the narrator was called
    assert (run / 'episode.json').read_bytes() == (source_run / 'episode.json').read_bytes()
    assert (run / 'draft.md').read_text() == DRAFT
    assert (run / 'draft.md').read_bytes() == (run / 'story.md').read_bytes()
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'passed' and meta.day == 1
