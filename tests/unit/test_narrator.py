import itertools
import json
import shutil
import time
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from typer.testing import CliRunner

from world_replies import commit_fixture_changes

from story_engine.agents import curator, narrator
from test_extract import fake
from story_engine.cli import app
from story_engine.runs import RunMeta
from story_engine.world.io import append_event, append_scene, load_state
from story_engine.world.models import Event, SceneRecord

ROOT = Path(__file__).resolve().parents[2]
EPISODE = dict(acts=[{'scene': 'A', 'pov': 'agnea'}, {'scene': 'B', 'pov': 'agnea'}], why='A choice resolved.')
# Scene A's events are 1 (round 1), 2 (round 2); no part-of-day events precede the day's first scene.
REPLY_A = json.dumps({'paragraphs': [
    {'text': '# A Festival Evening', 'rounds': [1], 'events': []},
    {'text': 'Agnea laughed.', 'rounds': [2], 'events': []},
]})
ACT_A = "# A Festival Evening<!-- r:1 -->\n\nAgnea laughed.<!-- r:2 -->\n"
STORY_A = "# A Festival Evening\n\nAgnea laughed.\n"
# Scene B's event is 4 (round 1); event 3 is the part-of-day transition since scene A.
REPLY_B = json.dumps({'paragraphs': [
    {'text': '# A Quiet Resolve', 'rounds': [], 'events': [3]},
    {'text': 'Agnea let the moment settle.', 'rounds': [1], 'events': []},
]})
ACT_B = "# A Quiet Resolve<!-- e:3 -->\n\nAgnea let the moment settle.<!-- r:1 -->\n"
STORY_B = "# A Quiet Resolve\n\nAgnea let the moment settle.\n"


@pytest.fixture
def world(tmp_path, monkeypatch):
    for name in ('config', 'prompts', 'cards'):
        shutil.copytree(ROOT / name, tmp_path / name)
    (tmp_path / 'docs').mkdir()
    shutil.copy(ROOT / 'docs/prd.md', tmp_path / 'docs/prd.md')
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
    commit_fixture_changes(world, state)
    (tmp_path / 'kb').mkdir()
    (tmp_path / 'kb/agnea.md').write_text('---\nname: Agnea\naliases: []\n---\n')
    fake(monkeypatch, [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[]), dict(call='contract', findings=[])])
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


def fake_narrator(monkeypatch, reply=REPLY_A):
    """`reply` is either reused for every call, or a list consumed one reply per call."""
    calls, options, lifecycle = [], [], []
    replies = iter(reply) if isinstance(reply, list) else itertools.repeat(reply)

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
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=next(replies), total_cost_usd=0.2)

    monkeypatch.setattr(narrator, 'ClaudeSDKClient', Client)
    return calls, options, lifecycle


def test_two_acts_previous_acts_and_story_join(world, monkeypatch):
    validation_calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[]), dict(call='contract', findings=[])])
    fake_curator(monkeypatch, [json.dumps(EPISODE)])
    calls, options, lifecycle = fake_narrator(monkeypatch, [REPLY_A, REPLY_B])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip().splitlines()[-1])
    assert lifecycle == ['enter', 'exit', 'enter', 'exit']
    assert len(calls) == 2 and all(options[i].tools == ['Read'] for i in range(2))
    request1 = json.loads(calls[0])
    assert request1['pov'] == 'agnea' and request1['previous_acts'] == []
    assert [beat['round'] for beat in request1['beats']] == [1, 2]
    assert [event['id'] for event in request1['beats'][0]['events']] == [1]
    assert [event['id'] for event in request1['beats'][1]['events']] == [2]
    request2 = json.loads(calls[1])
    assert request2['previous_acts'] == [STORY_A]
    assert [beat['round'] for beat in request2['beats']] == [1]
    assert [event['id'] for event in request2['beats'][0]['events']] == [4]
    assert [event['id'] for event in request2['part_of_day_events']] == [3]
    assert (run / 'acts/act_1.md').read_text() == ACT_A
    assert (run / 'acts/act_2.md').read_text() == ACT_B
    story = (run / 'story.md').read_text()
    assert story == STORY_A + '\n\n---\n\n' + STORY_B
    assert '<!--' not in story
    assert [json.loads(call)['call'] for call in validation_calls] == ['extract', 'verdicts', 'contract']
    sentences = json.loads(validation_calls[0])['sentences']
    assert any('Agnea laughed.' in row['text'] for row in sentences)
    assert any('Agnea let the moment settle.' in row['text'] for row in sentences)
    assert 'not_in_kb=0' in result.output
    assert (run / 'draft.md').read_text() == story
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'passed' and meta.day == 1
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    grounding = [event for event in trace if event['type'] == 'act_grounding']
    assert [event['act'] for event in grounding] == [1, 2]
    assert [event['cited_round_share'] for event in grounding] == [1.0, 1.0]
    assert grounding[0]['cited_rounds'] == [1, 2] and grounding[0]['cited_events'] == []
    assert grounding[1]['cited_rounds'] == [1] and grounding[1]['cited_events'] == [3]


def test_act_request_scopes_scene_and_transition_events(world, monkeypatch):
    reply = json.dumps({'paragraphs': [
        {'text': '# Agnea resolves it.', 'rounds': [], 'events': [3]},
        {'text': 'She smiled.', 'rounds': [1], 'events': []},
    ]})
    act_text = "# Agnea resolves it.<!-- e:3 -->\n\nShe smiled.<!-- r:1 -->\n"
    calls, options, lifecycle = fake_narrator(monkeypatch, reply=reply)
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'B', '--pov', 'agnea'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip().splitlines()[-1])
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
    assert (run / 'acts/act_1.md').read_text() == act_text
    assert not (run / 'draft.md').exists()
    assert not (run / 'episode.json').exists()
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'passed' and meta.day == 1


def test_paragraph_without_citation_rejected_then_retry_accepted(world, monkeypatch):
    bad = json.dumps({'paragraphs': [
        {'text': '# A Festival Evening', 'rounds': [1], 'events': []},
        {'text': 'Agnea laughed.', 'rounds': [], 'events': []},
    ]})
    calls, _, _ = fake_narrator(monkeypatch, [bad, REPLY_A])
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'A', '--pov', 'agnea'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip().splitlines()[-1])
    assert len(calls) == 2  # the bad reply, then the retry
    assert 'Grounding check failed' in calls[1]
    assert 'cite' in calls[1]
    assert (run / 'acts/act_1.md').read_text() == ACT_A


def test_citation_of_nonexistent_round_rejected(world, monkeypatch):
    bad = json.dumps({'paragraphs': [
        {'text': '# A Festival Evening', 'rounds': [1], 'events': []},
        {'text': 'Agnea laughed.', 'rounds': [5], 'events': []},  # scene A has rounds 1-2 only
    ]})
    calls, _, _ = fake_narrator(monkeypatch, [bad, bad])
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'A', '--pov', 'agnea'])
    assert result.exit_code == 1
    assert 'paragraph 2' in result.output
    assert len(calls) == 2  # one retry, then the final failure


def test_citation_of_nonexistent_event_rejected(world, monkeypatch):
    bad = json.dumps({'paragraphs': [
        {'text': '# A Festival Evening', 'rounds': [1], 'events': [99]},  # not a transition event
        {'text': 'Agnea laughed.', 'rounds': [2], 'events': []},
    ]})
    calls, _, _ = fake_narrator(monkeypatch, [bad, bad])
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'A', '--pov', 'agnea'])
    assert result.exit_code == 1
    assert 'paragraph 1' in result.output
    assert len(calls) == 2


def test_multiple_rounds_cited_render_as_range(world, monkeypatch):
    """Citing rounds [1, 2] in one paragraph renders as the range `<!-- r:1-2 -->`."""
    reply = json.dumps({'paragraphs': [
        {'text': '# A Festival Evening', 'rounds': [1, 2], 'events': []},
        {'text': 'Agnea laughed.', 'rounds': [1, 2], 'events': []},
    ]})
    expected = "# A Festival Evening<!-- r:1-2 -->\n\nAgnea laughed.<!-- r:1-2 -->\n"
    calls, _, _ = fake_narrator(monkeypatch, reply)
    result = CliRunner().invoke(
        app, ['world', 'tell', 'test', '--day', '1', '--act', 'A', '--pov', 'agnea'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip().splitlines()[-1])
    assert (run / 'acts/act_1.md').read_text() == expected
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    grounding = next(row for row in trace if row['type'] == 'act_grounding')
    assert grounding['cited_rounds'] == [1, 2] and grounding['cited_round_share'] == 1.0


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
    calls, _, _ = fake_narrator(monkeypatch, [REPLY_A, REPLY_B])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--episode-from', source_run.name])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip().splitlines()[-1])
    assert run != source_run
    assert len(calls) == 2  # the narrator was called, once per act
    assert (run / 'episode.json').read_bytes() == (source_run / 'episode.json').read_bytes()
    assert (run / 'acts/act_1.md').read_text() == ACT_A
    assert (run / 'acts/act_2.md').read_text() == ACT_B
    assert (run / 'story.md').read_text() == STORY_A + '\n\n---\n\n' + STORY_B
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
    validation_calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[]), dict(call='contract', findings=[])])
    fake_curator(monkeypatch, [json.dumps(EPISODE)])
    calls, _, _ = fake_narrator(monkeypatch, [REPLY_A, REPLY_B])
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1', '--stop-after', 'act:1'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip().splitlines()[-1])
    assert len(calls) == 1
    assert validation_calls == []
    act1_path = run / 'acts/act_1.md'
    assert act1_path.read_text() == ACT_A
    assert not (run / 'acts/act_2.md').exists()
    assert not (run / 'story.md').exists()
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'stopped'
    before_bytes = act1_path.read_bytes()
    before_mtime = act1_path.stat().st_mtime_ns

    time.sleep(0.01)
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--continue', run.name])
    assert result.exit_code == 0, result.output
    assert Path(result.output.strip().splitlines()[-1]) == run
    assert len(calls) == 2
    assert act1_path.read_bytes() == before_bytes
    assert act1_path.stat().st_mtime_ns == before_mtime
    assert (run / 'acts/act_2.md').read_text() == ACT_B
    assert (run / 'story.md').read_text() == STORY_A + '\n\n---\n\n' + STORY_B
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == 'passed'


@pytest.mark.parametrize('fix_rounds', [0, 1])
def test_validation_fixes_only_joined_text(world, monkeypatch, fix_rounds):
    import yaml
    from test_extract import claim
    from test_validation import verdict

    settings_path = Path('config/settings.yaml')
    settings = yaml.safe_load(settings_path.read_text())
    settings['validation_rounds'] = fix_rounds
    settings_path.write_text(yaml.safe_dump(settings))
    fake_curator(monkeypatch, [json.dumps(EPISODE)])
    fake_narrator(monkeypatch, [REPLY_A, REPLY_B] + [json.dumps(dict(edits=[dict(
        fixes=[1], old_string='Agnea laughed.', new_string='Agnea smiled.')]))])
    replies = [dict(call='extract', claims=[claim(1, 'canon_fact', entities=['agnea'])]),
               dict(call='verdicts', verdicts=[verdict(file='kb/agnea.md') | dict(evidence='name: Agnea')]),
               dict(call='contract', findings=[])]
    if fix_rounds:
        replies += [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[]), dict(call='contract', findings=[])]
    validation_calls, _, _ = fake(monkeypatch, replies)
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--day', '1'])
    assert result.exit_code == (0 if fix_rounds else 1), result.output
    run, = Path('runs').iterdir()
    joined = STORY_A + '\n\n---\n\n' + STORY_B
    assert (run / 'draft.md').read_text() == joined
    assert (run / 'acts/act_1.md').read_text() == ACT_A
    assert (run / 'acts/act_2.md').read_text() == ACT_B
    assert all(json.loads(call)['call'] != 'log' for call in validation_calls)
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    assert meta.status == ('passed' if fix_rounds else 'failed')
    assert (run / 'validation.json').exists() and (run / 'edits.json').exists()
    if fix_rounds:
        assert (run / 'story.md').read_text() == joined.replace('Agnea laughed.', 'Agnea smiled.')
    else:
        assert meta.error == 'validate failed: contradictions remain after 0 fix rounds'
        assert not (run / 'story.md').exists()
