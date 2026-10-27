import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.eval import world as evaluator
from story_engine.world.io import load_state, append_event, append_scene
from story_engine.world.models import Event, SceneRecord

ROOT = Path(__file__).resolve().parents[2]


def files(path):
    return {str(p.relative_to(path)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in path.rglob('*') if p.is_file()}


@pytest.fixture
def world(tmp_path, monkeypatch):
    for name in ('config', 'prompts'):
        shutil.copytree(ROOT / name, tmp_path / name)
    world = tmp_path / 'worlds/test'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    monkeypatch.chdir(tmp_path)
    return world


def fake(monkeypatch, replies):
    calls, options, life = [], [], []
    replies = iter(replies)

    class Client:
        def __init__(self, **kwargs):
            options.append(kwargs['options'])

        async def __aenter__(self):
            life.append('enter')
            return self

        async def __aexit__(self, *args):
            life.append('exit')

        async def query(self, request):
            calls.append(request)

        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake', structured_output=next(replies),
                                total_cost_usd=.1 * len(calls))

    monkeypatch.setattr(evaluator, 'ClaudeSDKClient', Client)
    return calls, options, life


def invoke(*args):
    return CliRunner().invoke(app, ['eval', 'world', *args])


def report():
    path = next(Path('runs').glob('*/world_report.json'))
    return path.parent, json.loads(path.read_bytes())


def finish(world, day=2, part='morning'):
    state = load_state(world)
    state.clock.day, state.clock.part = day, part
    # Seed the historical snapshot; these tests fabricate completed worlds.
    (world / "genesis.json").write_text(state.model_dump_json(indent=2))
    (world / "state.json").write_text(state.model_dump_json(indent=2))


@pytest.mark.parametrize('part', ['morning', 'night'])
def test_earlier_day_rejected_without_run(world, monkeypatch, part):
    finish(world, 3, part)
    calls, options, _ = fake(monkeypatch, [])
    before = files(world)
    result = invoke('test', '--day', '1')
    assert result.exit_code == 1
    assert 'test' in result.output
    assert 'only the latest simulated day can be checked' in result.output
    assert not Path('runs').exists()
    assert calls == options == []
    assert files(world) == before


@pytest.mark.parametrize('part,finished', [('morning', True), ('night', False)])
def test_default_day_and_read_only(world, monkeypatch, part, finished):
    finish(world, 2 if finished else 1, part)
    calls, options, life = fake(monkeypatch, [{'findings': []}])
    before, old_runs = files(world), files(Path('runs'))
    result = invoke('test')
    assert result.exit_code == 0, result.output
    run, data = report()
    assert data['day'] == 1 and data['completion'] is finished
    assert 'new_situations' not in data
    assert 'interactions_staged' not in result.output
    assert 'interactions_staged' not in (run / 'world_report.json').read_text()
    assert files(world) == before
    assert all(files(Path('runs'))[k] == v for k, v in old_runs.items())
    assert (run / 'retrieval.jsonl').exists() and (run / 'trace.jsonl').exists()
    meta = json.loads((run / 'meta.json').read_bytes())
    assert (meta['mode'], meta['world_id'], meta['day']) == ('world_eval', 'test', 1)
    assert len(options) == int(finished)
    assert life == (['enter', 'exit'] if finished else [])
    if finished:
        assert options[0].tools == options[0].allowed_tools == ['Read', 'Grep']
        assert options[0].output_format['type'] == 'json_schema'
        assert data['cost_usd'] == .1
    else:
        assert calls == [] and data['judge_status'] == 'skipped'
        assert data['overdue_situations'] is None
        assert data['cost_usd'] == 0


def test_metrics_and_full_judge_payload(world, monkeypatch):
    state = load_state(world)
    state.clock.day = 3
    state.situations[0].status = 'resolved'
    state.situations[1].due.day = 4
    new = state.situations[2].model_copy(deep=True)
    new.id, new.status, new.due.day = 'new', 'dropped', 2
    state.situations.append(new)
    # Seed the historical snapshot; these tests fabricate completed worlds.
    (world / "genesis.json").write_text(state.model_dump_json(indent=2))
    (world / "state.json").write_text(state.model_dump_json(indent=2))
    for i, day, scene, of in [(1, 1, None, None), (2, 2, None, 'agnea'),
                               (3, 2, 's', 'agnea'), (4, 2, None, None), (5, 3, None, 'agnea')]:
        append_event(world, Event(id=i, day=day, part='morning', place='cropdale',
                                 actor='world', type='world', content='Evidence.', intent=None,
                                 perceived_by=['agnea'], scene=scene, of=of))
    append_scene(world, SceneRecord(id='s', day=2, part='morning', place='cropdale',
                                   participants=['agnea'], first_event_id=3, last_event_id=3,
                                   rounds=7, end='part_over'))
    calls, _, _ = fake(monkeypatch, [{'findings': [dict(metric='continuity', event_ids=[1, 2],
                                                     state_refs=['arbitrary'], explanation='Unchecked.')]}])
    result = invoke('test', '--day', '2')
    assert result.exit_code == 0, result.output
    _, data = report()
    assert data['overdue_situations'] == ['stage_collapse_risk']
    assert 'new_situations' not in data
    assert data['counts'] == dict(scenes=1, scene_rounds=7, part_of_day_outcomes=1)
    payload = json.loads(calls[0])
    assert payload['events'] == [e.model_dump() for e in evaluator.read_events(world) if e.day == 2]
    assert payload['outcomes'] == [payload['events'][0]]
    assert [e['id'] for e in payload['previous_events']] == [1]
    assert 'start_state' not in payload
    assert payload['end_state'] == state.model_dump()
    assert payload['scenes'][0]['rounds'] == 7


def test_judge_input_excludes_op_only_events_and_keeps_visible_ops(world, monkeypatch):
    from story_engine.world.io import commit_event
    from story_engine.world.ops import ClockOp, PlaceOp
    from story_engine.world.permissions import Authority
    finish(world, 3)
    visible = []
    for day in (1, 2):
        commit_event(world, Event(
            id=0, day=day, part='night', place='cropdale', actor='world', type='state_change',
            content='', perceived_by=['agnea'], ops=[ClockOp(day=3, part='morning')]))
        visible.append(commit_event(world, Event(
            id=0, day=day, part='night', place='cropdale', actor='world', type='world',
            content='The stall opens.', perceived_by=['agnea'],
            ops=[PlaceOp(slug='cropdale', add_details=[f'Stall {day}'])]), authority=Authority('offscreen')))
    calls, _, _ = fake(monkeypatch, [{'findings': []}])
    result = invoke('test', '--day', '2')
    assert result.exit_code == 0, result.output
    payload = json.loads(calls[0])
    assert payload['previous_events'] == [visible[0].model_dump()]
    assert payload['events'] == [visible[1].model_dump()]
    assert payload['outcomes'] == []
    assert payload['events'][0]['ops'] == [op.model_dump() for op in visible[1].ops]


@pytest.mark.parametrize('recover', [False, True])
def test_unknown_event_retry_once(world, monkeypatch, recover):
    finish(world)
    bad = {'findings': [dict(metric='state_follows_log', event_ids=[999],
                             state_refs=['characters.throne.where'], explanation='Anything.') ]}
    calls, options, life = fake(monkeypatch, [bad, {'findings': []} if recover else bad])
    before = files(world)
    result = invoke('test')
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(calls) == 2 and 'unknown event ids: [999]' in calls[1]
    assert len(options) == 1 and life == ['enter', 'exit']
    run, data = report()
    assert data['completion'] is True
    assert data['judge_status'] == ('passed' if recover else 'failed')
    assert json.loads((run / 'meta.json').read_bytes())['status'] == data['judge_status']
    assert data['cost_usd'] == .2
    assert files(world) == before


@pytest.mark.parametrize('recover', [False, True])
@pytest.mark.parametrize('metric,event_ids,state_refs,error', [
    ('canon_and_scope', [], [], 'every finding must cite at least one event id or state_ref'),
    ('continuity', [1], [], 'continuity findings are not allowed on day 1'),
])
def test_reference_rules_retry_once(world, monkeypatch, recover, metric, event_ids, state_refs, error):
    day = 2 if event_ids == [4] else 1
    finish(world, day + 1)
    for i, event_day, scene, of in [(1, day, None, 'agnea'), (2, day, 's', 'agnea'),
                                     (3, day, None, None), (4, day - 1, None, 'agnea')]:
        append_event(world, Event(id=i, day=event_day, part='morning', place='cropdale',
                                 actor='world', type='world', content='Evidence.', intent=None,
                                 perceived_by=['agnea'], scene=scene, of=of))
    bad = {'findings': [dict(metric=metric, event_ids=event_ids, state_refs=state_refs,
                             explanation='Unchecked free text.')]}
    good = {'findings': [dict(metric='canon_and_scope', event_ids=[2], state_refs=[],
                              explanation='Unchecked free text.')]}
    calls, options, life = fake(monkeypatch, [bad, good if recover else bad])
    before = files(world)
    result = invoke('test')
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(calls) == 2
    assert error in calls[1]
    assert len(options) == 1 and life == ['enter', 'exit']
    run, data = report()
    assert data['judge_status'] == ('passed' if recover else 'failed')
    assert json.loads((run / 'meta.json').read_bytes())['status'] == data['judge_status']
    assert data['findings'] == (good['findings'] if recover else [])
    if not recover:
        assert 'after one retry' in data['error'] and error in data['error']
    assert files(world) == before


@pytest.mark.parametrize('metric,event_ids,state_refs', [
    ('canon_and_scope', [1], []),
    ('canon_and_scope', [2], ['characters.throne.where']),
    ('canon_and_scope', [], ['characters.throne.where']),
    ('canon_and_scope', [2], []),
])
def test_valid_reference_reply_passes(world, monkeypatch, metric, event_ids, state_refs):
    finish(world)
    for i, scene in [(1, None), (2, 's')]:
        append_event(world, Event(id=i, day=1, part='morning', place='cropdale',
                                 actor='world', type='world', content='Evidence.', intent=None,
                                 perceived_by=['agnea'], scene=scene, of='agnea'))
    good = {'findings': [dict(metric=metric, event_ids=event_ids, state_refs=state_refs,
                              explanation='Anything, including continuity on day 1.')]}
    calls, _, _ = fake(monkeypatch, [good])
    result = invoke('test')
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert report()[1]['findings'] == good['findings']
    assert 'interactions_staged' not in result.output
    run, _ = report()
    assert 'interactions_staged' not in (run / 'world_report.json').read_text()


def test_retired_metric_is_absent_from_judge_schema_and_prompt(world, monkeypatch):
    finish(world)
    _, options, _ = fake(monkeypatch, [{'findings': []}])
    result = invoke('test')
    assert result.exit_code == 0, result.output
    assert 'interactions_staged' not in json.dumps(options[0].output_format)
    assert 'interactions_staged' not in Path('prompts/world_judge.md').read_text()


def test_multiple_worlds_explicit_day_sequential(world, monkeypatch):
    finish(world)
    shutil.copytree(world, Path('worlds/other'))
    calls, options, life = fake(monkeypatch, [{'findings': []}, {'findings': []}])
    result = invoke('test', 'other', '--day', '1')
    assert result.exit_code == 0, result.output
    assert len(result.output.splitlines()) == 2
    assert len(calls) == len(options) == 2
    assert life == ['enter', 'exit', 'enter', 'exit']


def test_non_session_error_includes_diagnostic(world, monkeypatch):
    finish(world)

    class BrokenClient:
        def __init__(self, **kwargs):
            raise RuntimeError('test diagnostic')

    monkeypatch.setattr(evaluator, 'ClaudeSDKClient', BrokenClient)
    result = invoke('test')
    assert result.exit_code == 1
    assert report()[1]['error'] == 'RuntimeError: test diagnostic'


def test_stale_candidates_use_clock_order_and_cover_both_kinds(world):
    from story_engine.world.models import Commitment
    state = load_state(world)
    state.clock.day, state.clock.part = 1, 'evening'
    state.characters['agnea'].commitments = [
        Commitment(id='past', what='Perform', where='cropdale', day=1, part='afternoon'),
        Commitment(id='now', what='Stay', where='cropdale', day=1, part='evening'),
        Commitment(id='future', what='Return', where='cropdale', day=2, part='morning'),
    ]
    state.situations[0].status = 'open'
    state.situations[0].due.day, state.situations[0].due.part = 1, 'morning'
    state.situations[1].status = 'resolved'
    state.situations[2].due.day = 2
    rows = evaluator.stale_candidates(state, ['morning', 'afternoon', 'evening', 'night'])
    assert [row['id'] for row in rows] == ['past', state.situations[0].id]
    assert rows[0]['state_ref'] == 'characters.agnea.commitments.0'
    assert rows[1]['state_ref'] == 'situations.0'
    assert rows[0]['value']['what'] == 'Perform'


def test_event_sourced_judge_receives_candidates(world, monkeypatch):
    finish(world)
    calls, _, _ = fake(monkeypatch, [{'findings': []}])
    result = invoke('test')
    assert result.exit_code == 0, result.output
    payload = json.loads(calls[0])
    assert payload['event_sourced'] is True
    assert payload['stale_candidates'] == evaluator.stale_candidates(
        load_state(world), ['morning', 'afternoon', 'evening', 'night'])


def test_event_sourced_rejects_whereabouts_finding(world, monkeypatch):
    finish(world)
    bad = {'findings': [dict(metric='state_follows_log', event_ids=[],
                             state_refs=['characters.throne.where'], explanation='Moved.') ]}
    calls, _, _ = fake(monkeypatch, [bad, {'findings': []}])
    result = invoke('test')
    assert result.exit_code == 0, result.output
    assert 'supplied stale candidate state_refs' in calls[1]


def test_stale_commitment_finding_is_accepted_for_person(world, monkeypatch):
    from story_engine.world.models import Commitment, Person
    state = load_state(world)
    state.clock.day, state.clock.part = 2, 'morning'
    state.people['Guest'] = Person(where='cropdale', wants=['Listen'], commitments=[
        Commitment(id='guest-promise', what='Attend', where='cropdale', day=1, part='night')])
    (world / 'genesis.json').write_text(state.model_dump_json(indent=2))
    (world / 'state.json').write_text(state.model_dump_json(indent=2))
    good = {'findings': [dict(metric='state_follows_log', event_ids=[],
        state_refs=['people.Guest.commitments.0'],
        explanation='guest-promise expired without recorded fulfillment or release.')]}
    calls, _, _ = fake(monkeypatch, [good])
    result = invoke('test')
    assert result.exit_code == 0, result.output
    assert report()[1]['findings'] == good['findings']
    assert any(c['id'] == 'guest-promise' for c in json.loads(calls[0])['stale_candidates'])



def test_judge_schema_constrains_state_findings_to_candidate_refs():
    payload = dict(event_sourced=True, stale_candidates=[dict(state_ref='people.Guest.commitments.0')])
    schema = evaluator.judge_output(payload)['schema']['$defs']['Finding']
    other, state = schema['anyOf']
    assert other['properties']['metric']['enum'] == ['canon_and_scope', 'continuity']
    assert state['properties']['metric']['const'] == 'state_follows_log'
    assert state['properties']['state_refs']['items']['enum'] == ['people.Guest.commitments.0']
    assert state['properties']['state_refs']['minItems'] == 1
    payload['stale_candidates'] = []
    assert 'anyOf' not in evaluator.judge_output(payload)['schema']['$defs']['Finding']
    assert 'anyOf' not in evaluator.judge_output(dict(event_sourced=False))['schema']['$defs']['Finding']


def test_legacy_world_keeps_whereabouts_citations(world, monkeypatch):
    finish(world)
    (world / 'genesis.json').unlink()
    good = {'findings': [dict(metric='state_follows_log', event_ids=[],
                             state_refs=['characters.throne.where'], explanation='Legacy mismatch.')]}
    calls, options, _ = fake(monkeypatch, [good])
    result = invoke('test')
    assert result.exit_code == 0, result.output
    assert json.loads(calls[0])['event_sourced'] is False
    assert 'anyOf' not in options[0].output_format['schema']['$defs']['Finding']
    assert report()[1]['findings'] == good['findings']



@pytest.mark.parametrize('day', [1, 2])
def test_empty_candidates_skip_state_metric_without_losing_canon(world, monkeypatch, day):
    finish(world, day + 1)
    state = load_state(world)
    for member in [*state.characters.values(), *state.people.values()]:
        member.commitments = []
    for situation in state.situations:
        situation.status = 'resolved'
    (world / 'genesis.json').write_text(state.model_dump_json(indent=2))
    (world / 'state.json').write_text(state.model_dump_json(indent=2))
    noise = dict(metric='state_follows_log', event_ids=[999],
                 state_refs=['characters.throne.where'], explanation='Unrequested noise.')
    canon = dict(metric='canon_and_scope', event_ids=[],
                 state_refs=['people'], explanation='Canon evidence.')
    calls, _, _ = fake(monkeypatch, [{'findings': [noise, canon]}])
    result = invoke('test')
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert json.loads(calls[0])['metrics_to_judge'] == (
        ['canon_and_scope'] + (['continuity'] if day >= 2 else []))
    run, data = report()
    assert data['findings'] == [canon]
    events = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    ignored = next(e for e in events if e['type'] == 'state_findings_ignored')
    assert ignored['findings'] == [noise]
