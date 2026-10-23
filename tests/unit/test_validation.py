import json
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.agents.validation import Validation
from test_extract import ROOT, claim, fake, workspace as extract_workspace


@pytest.fixture
def workspace(extract_workspace):
    shutil.copytree(ROOT / "cards", Path("cards"))


def extracted():
    return dict(call='extract', claims=[
        claim(1, 'canon_fact'), claim(1, 'invented_detail'),
        claim(1, 'canon_fact'), claim(1, 'opinion_or_joke'), claim(1, 'canon_fact'),
    ])


def verdict(claim_id=0, kind='contradicted', file='kb/temenos.md'):
    return dict(claim_id=claim_id, evidence='name: Temenos' if file else '',
                reason='Uninspected reason.', verdict=kind, source=file)


def run_story():
    Path('input.md').write_bytes(b'Temenos made an assertion.\n\nNo entities here.\n')
    return CliRunner().invoke(app, ['eval', 'validate', 'input.md'])


def test_round_cli_and_single_session(workspace, monkeypatch):
    replies = [extracted(), dict(call='verdicts', verdicts=[
        verdict(4, 'supported'), verdict(2, 'not_in_kb', None), verdict(),
    ])]
    calls, options, life = fake(monkeypatch, replies)
    result = run_story()
    assert result.exit_code == 0, result.output
    assert 'contradicted=1' in result.output
    assert 'Uninspected quote. [kb/temenos.md]' in result.output
    assert 'not_in_kb=1' in result.output
    assert len(options) == 1 and life == ['enter', 'exit']
    assert len(calls) == 2
    first, second = map(json.loads, calls)
    assert first == dict(call='extract', sentences=[dict(
        sentence_id=1, text='Temenos made an assertion.', entities=['temenos'])])
    assert second.pop('sources') == {name: Path(name).read_text() for name in
                                      ('prompts/world_premise.md', 'cards/temenos.md')}
    assert second == dict(call='verdicts', claims=[
        dict(claim_id=i, **c) for i, c in enumerate(extracted()['claims']) if c['type'] == 'canon_fact'])
    schema = options[0].output_format['schema']
    assert schema['$defs']['ExtractReply']['properties']['call']['const'] == 'extract'
    assert schema['$defs']['VerdictReply']['properties']['call']['const'] == 'verdicts'
    assert options[0].tools == options[0].allowed_tools == ['Read', 'Grep']
    run = next(Path('runs').iterdir())
    assert (run / 'draft.md').read_bytes() == Path('input.md').read_bytes()
    data = json.loads((run / 'validation.json').read_text())
    expected = extracted()['claims']
    for i, v in [(0, verdict()), (2, verdict(2, 'not_in_kb', None)), (4, verdict(4, 'supported'))]:
        expected[i] |= {k: value for k, value in v.items() if k != 'claim_id'}
        expected[i]['claimed_verdict'] = None
    assert data == dict(rounds=[dict(round=1, claims=expected, not_in_kb=[expected[2]], contradicted=1, unverified=[])])
    assert Validation.model_validate(data).model_dump() == data
    meta = json.loads((run / 'meta.json').read_text())
    assert meta['mode'] == 'validate' and meta['status'] == 'passed'


@pytest.mark.parametrize('bad,error', [
    ([], 'exactly one verdict'),
    ([verdict(file='missing.md')], 'existing repo-relative file'),
    ([verdict(), verdict()], 'exactly one verdict'),
    ([verdict(1)], 'exactly one verdict'),
    ([verdict(file='../input.md')], 'existing repo-relative file'),
    ([verdict(file='/etc/hosts')], 'existing repo-relative file'),
])
@pytest.mark.parametrize('recover', [False, True])
def test_verdict_retry_once_and_failure(workspace, monkeypatch, bad, error, recover):
    extraction = dict(call='extract', claims=[claim(1, 'canon_fact')])
    invalid = dict(call='verdicts', verdicts=bad)
    corrected = dict(call='verdicts', verdicts=[verdict()])
    calls, options, life = fake(monkeypatch, [extraction, invalid, corrected if recover else invalid])
    result = run_story()
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(calls) == 3 and error in calls[2]
    assert len(options) == 1 and life == ['enter', 'exit']
    run = next(Path('runs').iterdir())
    meta = json.loads((run / 'meta.json').read_text())
    assert meta['status'] == ('passed' if recover else 'failed')
    if not recover:
        assert 'after one retry' in meta['error'] and error in meta['error']
        assert not (run / 'validation.json').exists()
    usage = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert [row['stage'] for row in usage if row['type'] == 'stage_usage'] == ['extract', 'verdicts', 'verdicts']


def test_empty_claims_still_two_calls(workspace, monkeypatch):
    calls, options, life = fake(monkeypatch, [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[])])
    Path('input.md').write_text('No known entities.')
    result = CliRunner().invoke(app, ['eval', 'validate', 'input.md'])
    assert result.exit_code == 0, result.output
    assert json.loads(calls[0]) == dict(call='extract', sentences=[])
    assert json.loads(calls[1]) == dict(call='verdicts', claims=[], sources={
        'prompts/world_premise.md': Path('prompts/world_premise.md').read_text()})
    assert len(options) == 1


def test_help():
    result = CliRunner().invoke(app, ['eval', 'validate', '--help'], color=False)
    assert result.exit_code == 0 and 'validate' in result.output and 'story_path' in result.output
    assert '--models' in result.output


@pytest.mark.parametrize('custom', [False, True])
def test_models_file_configures_validator(workspace, monkeypatch, custom):
    models_file = Path('config/models.yaml')
    config = yaml.safe_load(models_file.read_text())
    if custom:
        models_file = Path('config/custom_models.yaml')
        config['validator'] = dict(model=config['narrator']['model'], effort='low', thinking='adaptive')
        models_file.write_text(yaml.safe_dump(config))
    _, options, _ = fake(monkeypatch, [dict(call='extract', claims=[]),
                                       dict(call='verdicts', verdicts=[])])
    Path('input.md').write_text('Temenos made an assertion.')
    args = ['eval', 'validate', 'input.md']
    if custom:
        args += ['--models', str(models_file)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    role = config['validator']
    assert len(options) == 1
    assert options[0].model == role['model']
    assert options[0].effort == role['effort']
    assert options[0].thinking == {'type': 'adaptive' if role['thinking'] == 'adaptive' else 'disabled'}
    run = next(Path('runs').iterdir())
    meta = json.loads((run / 'meta.json').read_text())
    assert meta['models_file'] == str(models_file)
    assert meta['models']['validator'] == {**role, 'base_url': None, 'auth_token_env': None, 'retries': 1, 'max_turns': None, 'timeout_s': None}


def test_verdict_schema_order():
    from story_engine.agents.validation import Verdict, CheckedClaim

    expected = ['evidence', 'reason', 'verdict', 'source']
    assert list(Verdict.model_json_schema()['properties']) == ['claim_id', *expected]
    assert list(CheckedClaim.model_json_schema()['properties'])[-4:] == expected


@pytest.mark.parametrize('kind', ['supported', 'contradicted', 'not_in_kb'])
@pytest.mark.parametrize('evidence', ['This excerpt is absent.',
                                      'name: Temenos … This excerpt is absent.', '', '… ...'])
def test_missing_evidence_retries_once_then_fails(workspace, monkeypatch, kind, evidence):
    invalid = verdict(kind=kind) | dict(evidence=evidence)
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[claim(1, 'canon_fact')]),
                                   dict(call='verdicts', verdicts=[invalid]),
                                   dict(call='verdicts', verdicts=[invalid])])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert 'unverified=1' in result.output
    assert f'claimed_verdict={kind}' in result.output
    assert claim(1, 'canon_fact')['claim'] in result.output
    assert len(calls) == 3
    request = json.loads(calls[2])
    assert request['call'] == 'verdicts'
    assert request['claims'] == [dict(claim_id=0, **claim(1, 'canon_fact'))]
    assert request['errors'][0]['source'] == 'kb/temenos.md'
    assert 'Evidence was not found in kb/temenos.md' in calls[2]
    run = next(Path('runs').iterdir())
    assert json.loads((run / 'meta.json').read_text())['status'] == 'passed'
    report = json.loads((run / 'validation.json').read_text())['rounds'][0]
    checked = report['claims'][0]
    assert checked['verdict'] == 'unverified'
    assert checked['claimed_verdict'] == kind
    assert checked['evidence'] == evidence
    assert checked['reason'] == invalid['reason']
    assert checked['source'] == invalid['source']
    assert report['contradicted'] == 0
    assert report['unverified'] == [checked]
    events = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    failures = [row for row in events if row['type'] == 'evidence_check_failed']
    assert len(failures) == 2
    assert all({key: row[key] for key in ('claim_id', 'source', 'evidence')} ==
               dict(claim_id=0, source='kb/temenos.md', evidence=evidence) for row in failures)
    assert events.index(failures[0]) < events.index(failures[1])


@pytest.mark.parametrize('formatted,plain', [
    ('- **Occupation**: Thief, assassin of the [Blacksnakes](x.md)',
     'Occupation: Thief, assassin of the Blacksnakes'),
    ('Before\n- One detail\n* Another detail\n12. Final detail',
     'Before One detail Another detail Final detail'),
    ('## History\nA *quiet* _traveler_ arrives.', 'History A quiet traveler arrives.'),
    ('He said, “It’s ‘safe’ here.”', 'He said, "It\'s \'safe\' here."'),
])
@pytest.mark.parametrize('reverse', [False, True])
def test_markdown_evidence_passes(workspace, monkeypatch, formatted, plain, reverse):
    source, evidence = (plain, formatted) if reverse else (formatted, plain)
    path = Path('kb/temenos.md')
    path.write_text(path.read_text() + '\n' + source)
    reply = verdict() | dict(evidence=evidence)
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[claim(1, 'canon_fact')]),
                                   dict(call='verdicts', verdicts=[reply])])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 2


def test_bare_bracket_evidence_passes(workspace, monkeypatch):
    path = Path('kb/temenos.md')
    path.write_text(path.read_text() + '\n- [Mother](../../characters/throne/mother.md) – Co-leader and administrator')
    reply = verdict() | dict(evidence='[Mother] – Co-leader and administrator')
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[claim(1, 'canon_fact')]),
                                   dict(call='verdicts', verdicts=[reply])])
    result = run_story()
    assert len(calls) == 2
    assert result.exit_code == 0, result.output
    run = next(Path('runs').iterdir())
    checked = json.loads((run / 'validation.json').read_text())['rounds'][0]['claims'][0]
    assert checked == claim(1, 'canon_fact') | {
        k: v for k, v in reply.items() if k != 'claim_id'
    } | dict(claimed_verdict=None)


@pytest.mark.parametrize('ellipsis', ['…', '...'])
def test_ellipsis_evidence_passes(workspace, monkeypatch, ellipsis):
    path = Path('kb/temenos.md')
    path.write_text(path.read_text() + '\n**First fragment**.\nUnquoted passage.\nLast fragment.')
    reply = verdict() | dict(evidence=f'{ellipsis} First fragment. {ellipsis} Last fragment. {ellipsis}')
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[claim(1, 'canon_fact')]),
                                   dict(call='verdicts', verdicts=[reply])])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 2


@pytest.mark.parametrize('source', ['kb/temenos.md', 'cards/temenos.md', 'prompts/world_premise.md'])
def test_normalized_evidence_passes(workspace, monkeypatch, source):
    Path(source).write_text(Path(source).read_text() + '\nHe met [his colleague](../people/colleague.md)\n  before the journey.')
    reply = verdict(file=source) | dict(evidence='He met his colleague   before\nthe journey.')
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[claim(1, 'canon_fact')]),
                                   dict(call='verdicts', verdicts=[reply])])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 2


@pytest.mark.parametrize('source', ['prompts/world_judge.md', 'config/models.yaml',
                                    'cards/other.md', 'kb/../input.md'])
def test_disallowed_source_rejected(workspace, monkeypatch, source):
    if source == 'cards/other.md':
        Path(source).write_text('name: Temenos')
    invalid = dict(call='verdicts', verdicts=[verdict(file=source)])
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[claim(1, 'canon_fact')]),
                                   invalid, invalid])
    assert run_story().exit_code == 1
    assert len(calls) == 3 and 'source must name an existing repo-relative file' in calls[2]


@pytest.mark.parametrize('kind', ['supported', 'contradicted'])
def test_source_required(workspace, monkeypatch, kind):
    invalid = dict(call='verdicts', verdicts=[verdict(kind=kind, file=None)])
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[claim(1, 'canon_fact')]),
                                   invalid, invalid])
    assert run_story().exit_code == 1
    assert len(calls) == 3 and 'require a source' in calls[2]


@pytest.mark.parametrize('offset', [0, 1])
def test_only_claim_entity_traveler_cards_supplied(workspace, monkeypatch, offset):
    slugs = ['osvald', 'temenos', 'agnea', 'throne', 'hikari', 'ochette', 'castti', 'partitio']
    for slug in slugs:
        Path(f'kb/{slug}.md').write_text(f'---\nname: {slug.title()}\naliases: []\n---\n')
    Path('kb/other.md').write_text('---\nname: Other\naliases: []\n---\n')
    selected = slugs[offset::2]
    claims = [claim(1, 'canon_fact', selected + ['other']),
              claim(1, 'invented_detail', ['temenos'])]
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=claims),
                                   dict(call='verdicts', verdicts=[verdict()])])
    assert run_story().exit_code == 0
    sources = json.loads(calls[1])['sources']
    assert sources == {name: Path(name).read_text() for name in
                       ['prompts/world_premise.md', *[f'cards/{s}.md' for s in selected + ['temenos']]]}


@pytest.mark.parametrize('recover', [True, False])
def test_evidence_reask_only_failing_claim(workspace, monkeypatch, recover):
    claims = [claim(1, 'canon_fact'), claim(1, 'canon_fact')]
    invalid = verdict(1) | dict(evidence='Absent evidence.')
    replacement = verdict(1, 'supported') if recover else invalid
    calls, options, life = fake(monkeypatch, [
        dict(call='extract', claims=claims),
        dict(call='verdicts', verdicts=[verdict(0), invalid]),
        dict(call='verdicts', verdicts=[replacement]),
    ])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 3
    assert len(options) == 1 and life == ['enter', 'exit']
    assert json.loads(calls[2])['claims'] == [dict(claim_id=1, **claims[1])]
    run = next(Path('runs').iterdir())
    report = json.loads((run / 'validation.json').read_text())['rounds'][0]
    assert report['claims'][0] == claims[0] | {
        k: v for k, v in verdict(0).items() if k != 'claim_id'
    } | dict(claimed_verdict=None)
    assert report['contradicted'] == 1
    checked = report['claims'][1]
    assert checked['verdict'] == ('supported' if recover else 'unverified')
    assert checked['claimed_verdict'] == (None if recover else 'contradicted')
    assert checked['evidence'] == replacement['evidence']
    assert report['unverified'] == ([] if recover else [checked])


@pytest.mark.parametrize('bad', [[], [verdict(file='missing.md')],
                                 [verdict() | dict(verdict='unverified')]])
@pytest.mark.parametrize('recover', [True, False])
def test_evidence_reask_schema_and_source_retry(workspace, monkeypatch, bad, recover):
    invalid = verdict() | dict(evidence='Absent evidence.')
    bad_reply = dict(call='verdicts', verdicts=bad)
    calls, _, _ = fake(monkeypatch, [
        dict(call='extract', claims=[claim(1, 'canon_fact')]),
        dict(call='verdicts', verdicts=[invalid]), bad_reply,
        dict(call='verdicts', verdicts=[verdict()]) if recover else bad_reply,
    ])
    result = run_story()
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(calls) == 4
    assert 'Reply validation failed for verdicts' in calls[3]
    run = next(Path('runs').iterdir())
    assert (run / 'validation.json').exists() == recover


def test_all_evidence_failures_collected(workspace, monkeypatch):
    claims = [claim(1, 'canon_fact'), claim(1, 'canon_fact')]
    invalid = [verdict(i) | dict(evidence='Absent evidence.') for i in range(2)]
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=claims),
                                   dict(call='verdicts', verdicts=invalid),
                                   dict(call='verdicts', verdicts=invalid)])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 3
    request = json.loads(calls[2])
    assert request['claims'] == [dict(claim_id=i, **c) for i, c in enumerate(claims)]
    assert [error['claim_id'] for error in request['errors']] == [0, 1]
    run = next(Path('runs').iterdir())
    report = json.loads((run / 'validation.json').read_text())['rounds'][0]
    assert len(report['unverified']) == 2
    events = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert [row['claim_id'] for row in events if row['type'] == 'evidence_check_failed'] == [0, 1, 0, 1]
