import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from story_engine.agents import narrator, validation
from story_engine.agents.narrator import FixReply, _apply_edits, _check_edits
from story_engine.cli import app
from test_extract import claim, fake, workspace as extract_workspace
from test_validation import workspace, verdict, log_world, log_entry, log_reply, contract_finding


def setup_fake(monkeypatch, replies):
    result = fake(monkeypatch, replies)
    monkeypatch.setattr(narrator, 'ClaudeSDKClient', validation.ClaudeSDKClient)
    return result


def check(kind='contradicted'):
    return [dict(call='extract', claims=[claim(1, 'canon_fact')]),
            dict(call='verdicts', verdicts=[verdict(kind=kind)]),
            dict(call='contract', findings=[])]


def edit(old='assertion', new='correction'):
    return dict(edits=[dict(fixes=[1], old_string=old, new_string=new)])


def run(*args):
    return CliRunner().invoke(app, ['eval', 'validate', 'input.md', '--fix', *args])


def artifacts():
    directory = next(Path('runs').iterdir())
    return directory, json.loads((directory / 'meta.json').read_text())


def test_fix_clean(workspace, monkeypatch):
    original = 'Temenos made an assertion.\n\nTemenos waited.\n'
    Path('input.md').write_text(original)
    calls, options, life = setup_fake(monkeypatch, check() + [edit()] + check('supported'))
    result = run()
    assert result.exit_code == 0, result.output
    directory, meta = artifacts()
    assert meta['status'] == 'passed'
    assert (directory / 'story.md').read_text() == original.replace('assertion', 'correction')
    assert (directory / 'draft.md').read_text() == original
    report = json.loads((directory / 'validation.json').read_text())
    assert [r['round'] for r in report['rounds']] == [1, 2]
    assert json.loads(calls[4])['sentences'] == [dict(sentence_id=1, text='Temenos made an correction.', entities=['temenos'])]
    assert json.loads(calls[3])['text'] == original
    items = json.loads(calls[3])['fixes']
    assert items == [dict(id=1, quote='Uninspected quote.', claim='Uninspected assertion.',
                          reason='Uninspected reason.', evidence='name: Temenos', source='kb/temenos.md')]
    assert json.loads((directory / 'edits.json').read_text()) == [dict(round=1, fixes=items, old_string='assertion', new_string='correction')]
    assert options[1].tools == options[1].allowed_tools == ['Read']
    assert options[1].model == meta['models']['narrator']['model']
    for name in ('narrator_fix.md', 'style_spec.md', 'world_premise.md'):
        assert Path('prompts', name).read_text() in options[1].system_prompt
    assert Path('cards/temenos.md').read_text() in options[1].system_prompt
    assert life.count('enter') == 3
    trace = [json.loads(line) for line in (directory / 'trace.jsonl').read_text().splitlines()]
    usage = [row for row in trace if row.get('stage') == 'fix' and row['type'] == 'stage_usage']
    assert len(usage) == 1 and usage[0]['agent'] == 'narrator'
    assert 'call_cost_usd' in usage[0]


@pytest.mark.parametrize('old', ['missing', 'Temenos'])
def test_bad_match_retry_failure(workspace, monkeypatch, old):
    Path('input.md').write_text('Temenos assertion.\n\nTemenos waited.')
    calls, _, _ = setup_fake(monkeypatch, check() + [edit(old), edit(old)])
    result = run()
    assert result.exit_code == 1
    assert len(calls) == 5 and 'occur exactly once' in calls[-1]
    directory, meta = artifacts()
    assert meta['status'] == 'failed' and 'after one retry' in meta['error']
    assert (directory / 'validation.json').exists()
    assert json.loads((directory / 'edits.json').read_text()) == []
    assert not (directory / 'story.md').exists()


@pytest.mark.parametrize('limit', [0, 1])
def test_exhausted(workspace, monkeypatch, limit):
    Path('input.md').write_text('Temenos assertion.')
    calls, _, _ = setup_fake(monkeypatch, check() + ([edit()] + check() if limit else []))
    result = run('--rounds', str(limit))
    assert result.exit_code == 1
    directory, meta = artifacts()
    assert meta['status'] == 'failed'
    assert meta['error'] == f'contradictions remain after {limit} fix rounds'
    assert len(calls) == (7 if limit else 3)
    assert (directory / 'draft.md').read_text() == 'Temenos assertion.'
    assert len(json.loads((directory / 'validation.json').read_text())['rounds']) == limit + 1
    assert (directory / 'edits.json').exists() and not (directory / 'story.md').exists()


@pytest.mark.parametrize('kind', ['not_in_kb', 'unverified'])
def test_no_fix_for_uncertain(workspace, monkeypatch, kind):
    Path('input.md').write_text('Temenos assertion.')
    replies = check('not_in_kb')
    if kind == 'unverified':
        bad = dict(call='verdicts', verdicts=[verdict() | dict(evidence='missing evidence')])
        replies = [replies[0], bad, bad, dict(call='contract', findings=[])]
    calls, options, _ = setup_fake(monkeypatch, replies)
    result = run()
    assert result.exit_code == 0, result.output
    directory, meta = artifacts()
    assert meta['status'] == 'passed' and len(options) == 1
    assert (directory / 'story.md').read_text() == Path('input.md').read_text()
    assert json.loads((directory / 'edits.json').read_text()) == []


def test_persistent_fixer(workspace, monkeypatch):
    Path('input.md').write_text('Temenos assertion.')
    calls, options, _ = setup_fake(monkeypatch, check() + [edit()] + check() + [edit('correction', 'truth')] + check('supported'))
    assert run('--rounds', '2').exit_code == 0
    assert len(options) == 4  # three validator sessions, one fixer
    assert json.loads(calls[7])['text'] == 'Temenos correction.'
    directory, _ = artifacts()
    assert [r['round'] for r in json.loads((directory / 'validation.json').read_text())['rounds']] == [1, 2, 3]


def test_default_rounds_and_negative(workspace, monkeypatch):
    import yaml
    settings = Path('config/settings.yaml')
    data = yaml.safe_load(settings.read_text())
    data['validation_rounds'] = 0
    settings.write_text(yaml.safe_dump(data))
    Path('input.md').write_text('Temenos assertion.')
    calls, _, _ = setup_fake(monkeypatch, check())
    assert run('--rounds', '-1').exit_code == 2
    assert calls == []
    assert run().exit_code == 1 and len(calls) == 3
    assert artifacts()[1]['error'] == 'contradictions remain after 0 fix rounds'


def test_log_only_fix(log_world, monkeypatch):
    initial = [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[]),
               log_reply(log_entry(verdict='contradicted', events=[])),
               dict(call='contract', findings=[])]
    clean = [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[]),
             dict(call='log', paragraphs=[dict(id=1, lines=[])]),
             dict(call='contract', findings=[])]
    calls, _, _ = setup_fake(monkeypatch, initial + [edit('No entities here.', 'He waited.')] + clean)
    result = run('--world', 'tiny', '--scene', 'chosen')
    assert result.exit_code == 0, result.output
    assert json.loads(calls[4])['fixes'] == [dict(id=1, quote='No entities here.', reason='Same action.', scene='chosen', paragraph=2)]
    assert json.loads(calls[7])['paragraphs'] == [dict(id=1, text='“Hello,” he said.\nHe waited.')]


def test_contract_only_fix(workspace, monkeypatch):
    original = 'Temenos waited.\n\nA second paragraph.'
    Path('input.md').write_text(original)
    finding = contract_finding(quote='A second paragraph.', kind='meta')
    clean = [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[])]
    calls, _, _ = setup_fake(monkeypatch, clean + [dict(call='contract', findings=[finding]),
        edit('A second paragraph.', 'The wind fell silent.')] + clean + [dict(call='contract', findings=[])])
    result = run()
    assert result.exit_code == 0, result.output
    assert json.loads(calls[3])['fixes'] == [dict(id=1, **finding)]
    assert json.loads(calls[6])['paragraphs'] == [dict(id=1, text='The wind fell silent.')]
    directory, meta = artifacts()
    assert meta['status'] == 'passed'
    assert (directory / 'story.md').read_text() == original.replace('A second paragraph.', 'The wind fell silent.')
    report = validation.Validation.model_validate_json((directory / 'validation.json').read_text())
    assert [round.contradicted for round in report.rounds] == [1, 0]
    assert report.rounds[1].contract == []
    assert json.loads((directory / 'edits.json').read_text()) == [dict(
        round=1, fixes=[dict(id=1, **finding)], old_string='A second paragraph.',
        new_string='The wind fell silent.')]


@pytest.mark.parametrize('text,edits,expected,changed', [
    ('A.\n\nB.\n\nC.', [('B.', '')], 'A.\n\n\n\nC.', 'A.\n\nC.'),
    ('A.\n\nB.', [('B.', '')], 'A.\n\n', 'A.'),
    ('A.\n\nB.', [('A.', '')], '\n\nB.', 'B.'),
    ('A.\n\nB.', [('A.', 'X.\n\nY.')], 'X.\n\nY.\n\nB.', 'X.\n\nY.'),
    ('A.\n\nB.\n\nC.', [('C.', 'Long.'), ('A.', 'Z.')], 'Z.\n\nB.\n\nLong.', 'Z.\n\nLong.'),
    ('A.\n\nB.', [('A.\n\nB.', '')], '', ''),
])
def test_changed_paragraphs(text, edits, expected, changed):
    reply = FixReply(edits=[dict(fixes=[1], old_string=a, new_string=b) for a, b in edits])
    _check_edits(reply, text, [dict(id=1)])
    assert _apply_edits(text, reply.edits) == (expected, changed)


def test_data_problems_collected():
    reply = FixReply(edits=[dict(fixes=[9], old_string='abc', new_string=''),
                           dict(fixes=[], old_string='bc', new_string=''),
                           dict(fixes=[], old_string='', new_string='')])
    with pytest.raises(ValueError) as error:
        _check_edits(reply, 'abc', [dict(id=1)])
    for fragment in ('unknown fix ids', 'uncovered fix ids', 'overlap', 'non-empty'):
        assert fragment in str(error.value)
