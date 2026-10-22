import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from typer.testing import CliRunner

from story_engine.agents import curator
from story_engine.cli import app
from story_engine.runs import RunMeta
from story_engine.world.io import append_event, append_scene, load_state, save_state
from story_engine.world.models import Event, SceneRecord

ROOT = Path(__file__).resolve().parents[2]
VALID = dict(acts=[{'scene': '2', 'pov': 'agnea'}, {'scene': '3', 'pov': 'throne'}], why='A choice resolved.')


@pytest.fixture
def world(tmp_path, monkeypatch):
    for name in ('config', 'prompts'):
        shutil.copytree(ROOT / name, tmp_path / name)
    world = tmp_path / 'worlds/test'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    append_event(world, Event(id=1, day=1, part='morning', place='cropdale', scene='2',
                             actor='agnea', type='action', content='Agnea waves.',
                             intent='Greet', perceived_by=['agnea']))
    append_event(world, Event(id=2, day=1, part='morning', place='cropdale', scene='2',
                             actor='agnea', type='speech', content='Agnea calls out.',
                             intent='Invite', perceived_by=['agnea']))
    append_event(world, Event(id=3, day=1, part='afternoon', place='cropdale',
                             actor='world', type='world', content='The bell rings.',
                             perceived_by=['throne']))
    append_event(world, Event(id=4, day=1, part='evening', place='cropdale', scene='3',
                             actor='agnea', type='action', content='Agnea sits beside Throné.',
                             intent='Rest', perceived_by=['agnea', 'throne']))
    append_event(world, Event(id=5, day=1, part='evening', place='cropdale', scene='3',
                             actor='throne', type='speech', content='Throné speaks quietly.',
                             intent='Open up', perceived_by=['agnea', 'throne']))
    append_scene(world, SceneRecord(id='2', day=1, part='morning', place='cropdale',
                                    participants=['agnea'], first_event_id=1, last_event_id=2,
                                    rounds=2, end='one_left'))
    append_scene(world, SceneRecord(id='3', day=1, part='evening', place='cropdale',
                                    participants=['agnea', 'throne'], first_event_id=4, last_event_id=5,
                                    rounds=2, end='one_left'))
    state = load_state(world)
    state.clock.day = 2
    save_state(world, state)
    monkeypatch.chdir(tmp_path)
    return world


def fake(monkeypatch, replies):
    calls, options, lifecycle = [], [], []
    replies = iter(replies)

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
            yield ResultMessage('success', 1, 1, False, 1, 'fake',
                                result=next(replies), total_cost_usd=.1 * len(calls))

    monkeypatch.setattr(curator, 'ClaudeSDKClient', Client)
    return calls, options, lifecycle


def test_valid_reply(world, monkeypatch):
    calls, options, lifecycle = fake(monkeypatch, [json.dumps(VALID)])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--stop-after', 'curate'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert curator.Episode.model_validate_json((run / 'episode.json').read_bytes()).model_dump() == VALID
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert (meta.mode, meta.world_id, meta.day) == ('simulation', 'test', 1)
    assert meta.status == 'stopped'
    assert len(options) == 1 and lifecycle == ['enter', 'exit']
    assert options[0].tools == options[0].allowed_tools == []
    assert options[0].thinking == {'type': 'disabled'} and options[0].effort == 'medium'
    payload = json.loads(calls[0])['events']
    assert payload[0]['scene'] == '2' and payload[0]['part'] == 'morning' and payload[0]['place'] == 'cropdale'
    assert payload[0]['participants'] == ['agnea'] and payload[0]['rounds'] == 2 and payload[0]['end'] == 'one_left'
    assert payload[0]['events'][0] == dict(id=1, part='morning', place='cropdale', actor='agnea',
                                           type='action', content='Agnea waves.', intent='Greet')
    assert payload[1] == dict(id=3, part='afternoon', place='cropdale', actor='world',
                              type='world', content='The bell rings.')
    assert 'intent' not in payload[1]
    assert payload[2]['scene'] == '3'
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert [row['call_cost_usd'] for row in trace if row['type'] == 'stage_usage'] == [.1]


@pytest.mark.parametrize('change,reason', [
    ({'acts': [{'scene': '2', 'pov': 'agnea'}, {'scene': '99', 'pov': 'throne'}]}, 'unknown scene id'),
    ({'acts': [{'scene': '2', 'pov': 'agnea'}, {'scene': '2', 'pov': 'agnea'}]}, 'not repeat'),
    ({'acts': [{'scene': '3', 'pov': 'throne'}, {'scene': '2', 'pov': 'agnea'}]}, 'chronological order'),
    ({'acts': [{'scene': '2', 'pov': 'shopkeeper'}, {'scene': '3', 'pov': 'throne'}]}, 'main character'),
])
def test_retry(world, monkeypatch, change, reason):
    calls, options, _ = fake(monkeypatch, [json.dumps(VALID | change), json.dumps(VALID)])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1', '--stop-after', 'curate'])
    assert result.exit_code == 0, result.output
    assert reason in calls[1] and len(options) == 1
    trace = [json.loads(line) for line in (Path(result.output.strip()) / 'trace.jsonl').read_text().splitlines()]
    assert [row['call_cost_usd'] for row in trace if row['type'] == 'stage_usage'] == [.1, .1]


def test_act_pov_not_participant_of_its_scene(world, monkeypatch):
    invalid = VALID | {'acts': [{'scene': '2', 'pov': 'throne'}, {'scene': '3', 'pov': 'throne'}]}
    calls, _, _ = fake(monkeypatch, [json.dumps(invalid), json.dumps(VALID)])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1', '--stop-after', 'curate'])
    assert result.exit_code == 0, result.output
    assert 'participant of scene 2' in calls[1]


def test_skipping_a_scene_is_the_curators_call(monkeypatch, tmp_path):
    """D27: which scenes an arc depends on is a judgment, not a code rule; skipping scene 2 is accepted."""
    for name in ('config', 'prompts'):
        shutil.copytree(ROOT / name, tmp_path / name)
    world = tmp_path / 'worlds/test'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    for scene_id in ('1', '2', '3', '4'):
        event_id = int(scene_id)
        append_event(world, Event(id=event_id, day=1, part='morning', place='cropdale', scene=scene_id,
                                 actor='agnea', type='action', content=f'Scene {scene_id}.',
                                 intent='Act', perceived_by=['agnea', 'throne']))
        append_scene(world, SceneRecord(id=scene_id, day=1, part='morning', place='cropdale',
                                        participants=['agnea', 'throne'], first_event_id=event_id,
                                        last_event_id=event_id, rounds=1, end='one_left'))
    state = load_state(world)
    state.clock.day = 2
    save_state(world, state)
    monkeypatch.chdir(tmp_path)
    skipping = dict(acts=[{'scene': '1', 'pov': 'agnea'}, {'scene': '3', 'pov': 'agnea'},
                          {'scene': '4', 'pov': 'agnea'}], why='The scenes that matter.')
    calls, _, _ = fake(monkeypatch, [json.dumps(skipping)])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1', '--stop-after', 'curate'])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    episode = curator.Episode.model_validate_json((Path(result.output.strip()) / 'episode.json').read_bytes())
    assert [act.scene for act in episode.acts] == ['1', '3', '4']


def test_absent_pov_final_error(world, monkeypatch):
    invalid = VALID | {'acts': [{'scene': '2', 'pov': 'throne'}, {'scene': '3', 'pov': 'throne'}]}
    calls, _, _ = fake(monkeypatch, [json.dumps(invalid)] * 2)
    result = CliRunner().invoke(app, ['world', 'tell', 'test'])
    assert result.exit_code == 1 and 'participant of scene 2' in result.output
    assert len(calls) == 2
    run = next(Path('runs').iterdir())
    assert not (run / 'episode.json').exists()
    assert RunMeta.model_validate_json((run / 'meta.json').read_bytes()).status == 'failed'


def test_incomplete_day(world, monkeypatch):
    calls, _, _ = fake(monkeypatch, [])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '2'])
    assert result.exit_code == 1 and 'not yet completed' in result.output
    assert calls == [] and not Path('runs').exists()


def test_day_with_no_scene_records_exits_1(tmp_path, monkeypatch):
    for name in ('config', 'prompts'):
        shutil.copytree(ROOT / name, tmp_path / name)
    world = tmp_path / 'worlds/test'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    append_event(world, Event(id=1, day=1, part='morning', place='cropdale',
                             actor='world', type='world', content='The festival opens.',
                             perceived_by=['agnea', 'throne']))
    state = load_state(world)
    state.clock.day = 2
    save_state(world, state)
    monkeypatch.chdir(tmp_path)
    calls, _, _ = fake(monkeypatch, [])
    result = CliRunner().invoke(app, ['world', 'tell', 'test'])
    assert result.exit_code == 1
    assert 'Day 1 has no scene records' in result.output
    assert calls == [] and not Path('runs').exists()


def test_pov_display_name_normalized():
    from story_engine.agents.curator import Act
    assert Act(scene='1', pov='Throné').pov == 'throne'


def test_pov_full_name_resolves_to_slug():
    from story_engine.agents.curator import Act, Episode, validate_episode
    from story_engine.world.models import SceneRecord
    scenes = [
        SceneRecord(id='1', day=1, part='morning', place='cropdale', participants=['agnea', 'throne'],
                   first_event_id=1, last_event_id=2, rounds=1, end='quiet'),
        SceneRecord(id='2', day=1, part='afternoon', place='cropdale', participants=['agnea', 'throne'],
                   first_event_id=3, last_event_id=4, rounds=1, end='quiet'),
    ]
    episode = validate_episode(
        Episode(acts=[Act(scene='1', pov='Throné Anguis'), Act(scene='2', pov='agnea')], why='x'),
        scenes, ['agnea', 'throne'],
    )
    assert episode.acts[0].pov == 'throne'
