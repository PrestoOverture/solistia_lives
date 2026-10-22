import itertools
import json
import shutil
import time
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
EPISODE = dict(acts=[{'scene': 'A', 'pov': 'agnea'}, {'scene': 'B', 'pov': 'agnea'}], why='A choice resolved.')
# Scene A's events are 1 (round 1), 2 (round 2); no part-of-day events precede the day's first scene.
DRAFT = "# A Festival Evening<!-- r:1 -->\n\nAgnea laughed.<!-- r:2 -->\n"
STORY_PART = "# A Festival Evening\n\nAgnea laughed.\n"
# Scene B's event is 4 (round 1); event 3 is the part-of-day transition since scene A.
DRAFT2 = "# A Quiet Resolve<!-- e:3 -->\n\nAgnea let the moment settle.<!-- r:1 -->\n"
STORY_PART2 = "# A Quiet Resolve\n\nAgnea let the moment settle.\n"


@pytest.fixture
def world(tmp_path, monkeypatch):
    for name in ('config', 'prompts', 'cards'):
        shutil.copytree(ROOT / name, tmp_path / name)
    world = tmp_path / 'worlds/test'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    append_event(world, Event(id=1, day=1, part='morning', place='cropdale', scene='A', round=1,
                             actor='agnea', type='action', content='Agnea waves.',
                             intent='Greet', perceived_by=['agnea', 'throne']))
    append_event(world, Event(id=2, day=1, part='morning', place='cropdale', scene='A', round=2,
                             actor='throne', type='speech', content='Throné answers.',
                             intent='Chat', perceived_by=['agnea', 'throne']))
    append_event(world, Event(id=3, day=1, part='afternoon', place='cropdale',
                             actor='world', type='world', content='The bell rings.',
                             perceived_by=['agnea', 'throne']))
    append_event(world, Event(id=4, day=1, part='evening', place='cropdale', scene='B', round=1,
                             actor='agnea', type='action', content='Agnea resolves it.',
                             intent='Resolve', perceived_by=['agnea', 'throne']))
    append_event(world, Event(id=5, day=1, part='night', place='cropdale', scene='C', round=1,
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
    """`draft` is either reused for every call, or a list consumed one draft per call."""
    calls, options, lifecycle = [], [], []
    drafts = iter(draft) if isinstance(draft, list) else itertools.repeat(draft)

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
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=next(drafts), total_cost_usd=0.2)

    monkeypatch.setattr(narrator, 'ClaudeSDKClient', Client)
    return calls, options, lifecycle


def test_two_acts_previous_acts_and_story_join(world, monkeypatch):
    fake_curator(monkeypatch, [json.dumps(EPISODE)])
    calls, options, lifecycle = fake_narrator(monkeypatch, [DRAFT, DRAFT2])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert lifecycle == ['enter', 'exit', 'enter', 'exit']
    assert len(calls) == 2 and all(options[i].tools == ['Read'] for i in range(2))
    request1 = json.loads(calls[0])
    assert request1['pov'] == 'agnea' and request1['previous_acts'] == []
    assert [beat['round'] for beat in request1['beats']] == [1, 2]
    assert [event['id'] for event in request1['beats'][0]['events']] == [1]
    assert [event['id'] for event in request1['beats'][1]['events']] == [2]
    request2 = json.loads(calls[1])
    assert request2['previous_acts'] == [STORY_PART]
    assert [beat['round'] for beat in request2['beats']] == [1]
    assert [event['id'] for event in request2['beats'][0]['events']] == [4]
    assert [event['id'] for event in request2['part_of_day_events']] == [3]
    assert (run / 'acts/act_1.md').read_text() == DRAFT
    assert (run / 'acts/act_2.md').read_text() == DRAFT2
    story = (run / 'story.md').read_text()
    assert story == STORY_PART + '\n\n---\n\n' + STORY_PART2
    assert '<!--' not in story
    assert not (run / 'draft.md').exists()
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'passed' and meta.day == 1
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    grounding = [event for event in trace if event['type'] == 'act_grounding']
    assert [event['act'] for event in grounding] == [1, 2]
    assert [event['cited_round_share'] for event in grounding] == [1.0, 1.0]
    assert grounding[0]['cited_rounds'] == [1, 2] and grounding[0]['cited_events'] == []
    assert grounding[1]['cited_rounds'] == [1] and grounding[1]['cited_events'] == [3]


def test_act_request_scopes_scene_and_transition_events(world, monkeypatch):
    draft = '# Agnea resolves it.<!-- e:3 -->\n\nShe smiled.<!-- r:1 -->\n'
    calls, options, lifecycle = fake_narrator(monkeypatch, draft=draft)
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'B', '--pov', 'agnea'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert lifecycle == ['enter', 'exit']
    assert options[0].tools == options[0].allowed_tools == ['Read']
    request = json.loads(calls[0])
    assert request['pov'] == 'agnea'
    assert [beat['round'] for beat in request['beats']] == [1]
    assert [event['id'] for event in request['beats'][0]['events']] == [4]
    assert [event['intent'] for event in request['beats'][0]['events']] == ['Resolve']
    assert [event['id'] for event in request['part_of_day_events']] == [3]
    assert [event['intent'] for event in request['part_of_day_events']] == [None]
    assert request['previous_acts'] == []
    assert (run / 'acts/act_1.md').read_text() == draft
    assert not (run / 'draft.md').exists()
    assert not (run / 'episode.json').exists()
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'passed' and meta.day == 1


def test_missing_marker_rejected_then_retry_accepted(world, monkeypatch):
    bad = "# A Festival Evening<!-- r:1 -->\n\nAgnea laughed.\n"  # second paragraph has no marker
    good = DRAFT
    calls, _, _ = fake_narrator(monkeypatch, [bad, good])
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'A', '--pov', 'agnea'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert len(calls) == 2  # the bad draft, then the retry
    assert 'Grounding check failed' in calls[1]
    assert 'paragraph 2' in calls[1]
    assert (run / 'acts/act_1.md').read_text() == good


def test_citation_of_nonexistent_round_rejected(world, monkeypatch):
    bad = "# A Festival Evening<!-- r:1 -->\n\nAgnea laughed.<!-- r:5 -->\n"  # scene A has rounds 1-2 only
    calls, _, _ = fake_narrator(monkeypatch, [bad, bad])
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'A', '--pov', 'agnea'])
    assert result.exit_code == 1
    assert 'paragraph 2' in result.output
    assert len(calls) == 2  # one retry, then the final failure


def test_round_range_marker_accepted(world, monkeypatch):
    """`<!-- r:1-2 -->` cites both of scene A's rounds in one marker."""
    draft = "# A Festival Evening<!-- r:1-2 -->\n\nAgnea laughed.<!-- r:1-2 -->\n"
    calls, _, _ = fake_narrator(monkeypatch, draft)
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'A', '--pov', 'agnea'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert (run / 'acts/act_1.md').read_text() == draft
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    grounding = next(row for row in trace if row['type'] == 'act_grounding')
    assert grounding['cited_rounds'] == [1, 2] and grounding['cited_round_share'] == 1.0


def test_dialogue_without_speech_citation_rejected(world, monkeypatch):
    # Scene B's only round (1) has an action event (4), and the part-of-day event (3) is a
    # world event: no round or event here contains speech.
    bad = '# Agnea resolves it.<!-- e:3 -->\n\nShe said, "It is done."<!-- r:1 -->\n'
    calls, _, _ = fake_narrator(monkeypatch, [bad, bad])
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'B', '--pov', 'agnea'])
    assert result.exit_code == 1
    assert 'paragraph 2' in result.output
    assert 'dialogue' in result.output
    assert len(calls) == 2


def test_act_only_pov_events_carry_intent(world, monkeypatch):
    calls, _, _ = fake_narrator(monkeypatch)
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'A', '--pov', 'agnea'])
    assert result.exit_code == 0, result.output
    request = json.loads(calls[0])
    events = [event for beat in request['beats'] for event in beat['events']]
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
    calls, _, _ = fake_narrator(monkeypatch, [DRAFT, DRAFT2])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--episode-from', source_run.name])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert run != source_run
    assert len(calls) == 2  # the narrator was called, once per act
    assert (run / 'episode.json').read_bytes() == (source_run / 'episode.json').read_bytes()
    assert (run / 'acts/act_1.md').read_text() == DRAFT
    assert (run / 'acts/act_2.md').read_text() == DRAFT2
    assert (run / 'story.md').read_text() == STORY_PART + '\n\n---\n\n' + STORY_PART2
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'passed' and meta.day == 1


def test_episode_from_rejects_old_format(world, monkeypatch):
    fake_curator(monkeypatch, [json.dumps(EPISODE)])
    source = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1', '--stop-after', 'curate'])
    assert source.exit_code == 0, source.output
    source_run = Path(source.output.strip())
    (source_run / 'episode.json').write_text(
        json.dumps({'scenes': ['A', 'B'], 'pov': 'agnea', 'why': 'old format'}), encoding='utf-8',
    )
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--episode-from', source_run.name])
    assert result.exit_code == 1
    assert 'old whole-episode format' in result.output


def test_stop_after_act_then_continue(world, monkeypatch):
    fake_curator(monkeypatch, [json.dumps(EPISODE)])
    calls, _, _ = fake_narrator(monkeypatch, [DRAFT, DRAFT2])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1', '--stop-after', 'act:1'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert len(calls) == 1
    act1_path = run / 'acts/act_1.md'
    assert act1_path.read_text() == DRAFT
    assert not (run / 'acts/act_2.md').exists()
    assert not (run / 'story.md').exists()
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'stopped'
    before_bytes = act1_path.read_bytes()
    before_mtime = act1_path.stat().st_mtime_ns

    time.sleep(0.01)
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--continue', run.name])
    assert result.exit_code == 0, result.output
    assert Path(result.output.strip()) == run
    assert len(calls) == 2
    assert act1_path.read_bytes() == before_bytes
    assert act1_path.stat().st_mtime_ns == before_mtime
    assert (run / 'acts/act_2.md').read_text() == DRAFT2
    assert (run / 'story.md').read_text() == STORY_PART + '\n\n---\n\n' + STORY_PART2
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'passed'
