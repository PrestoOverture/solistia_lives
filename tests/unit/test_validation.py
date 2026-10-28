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


def contract_reply(*findings):
    return dict(call='contract', findings=list(findings))


def run_story():
    Path('input.md').write_bytes(b'Temenos made an assertion.\n\nNo entities here.\n')
    return CliRunner().invoke(app, ['eval', 'validate', 'input.md'])


def test_round_cli_and_validator_sessions(workspace, monkeypatch):
    replies = [extracted(), dict(call='verdicts', verdicts=[
        verdict(4, 'supported'), verdict(2, 'not_in_kb', None), verdict(),
    ])]
    calls, options, life = fake(monkeypatch, replies + [contract_reply()])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert 'contradicted=1' in result.output
    assert 'Uninspected quote. [kb/temenos.md]' in result.output
    assert 'not_in_kb=1' in result.output
    assert len(options) == 2 and life == ['enter', 'exit', 'enter', 'exit']
    assert len(calls) == 3
    first, second, _ = map(json.loads, calls)
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
    assert data == dict(rounds=[dict(round=1, claims=expected, not_in_kb=[expected[2]], contradicted=1, unverified=[], log=None, contract=[])])
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
    calls, options, life = fake(monkeypatch, [extraction, invalid, corrected if recover else invalid] + [contract_reply()])
    result = run_story()
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(calls) == (3 + int(recover)) and error in calls[2]
    assert len(options) == 1 + int(recover)
    assert life == ['enter', 'exit'] * (1 + int(recover))
    run = next(Path('runs').iterdir())
    meta = json.loads((run / 'meta.json').read_text())
    assert meta['status'] == ('passed' if recover else 'failed')
    if not recover:
        assert 'after one retry' in meta['error'] and error in meta['error']
        assert not (run / 'validation.json').exists()
    usage = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert [row['stage'] for row in usage if row['type'] == 'stage_usage'] == ['extract', 'verdicts', 'verdicts'] + (['contract'] if recover else [])


def test_empty_claims_still_checks_contract(workspace, monkeypatch):
    calls, options, life = fake(monkeypatch, [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[])] + [contract_reply()])
    Path('input.md').write_text('No known entities.')
    result = CliRunner().invoke(app, ['eval', 'validate', 'input.md'])
    assert result.exit_code == 0, result.output
    assert json.loads(calls[0]) == dict(call='extract', sentences=[])
    assert json.loads(calls[1]) == dict(call='verdicts', claims=[], sources={
        'prompts/world_premise.md': Path('prompts/world_premise.md').read_text()})
    assert len(options) == 2


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
                                       dict(call='verdicts', verdicts=[])] + [contract_reply()])
    Path('input.md').write_text('Temenos made an assertion.')
    args = ['eval', 'validate', 'input.md']
    if custom:
        args += ['--models', str(models_file)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    role = config['validator']
    assert len(options) == 2
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
                                   dict(call='verdicts', verdicts=[invalid])] + [contract_reply()])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert 'unverified=1' in result.output
    assert f'claimed_verdict={kind}' in result.output
    assert claim(1, 'canon_fact')['claim'] in result.output
    assert len(calls) == 4
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
                                   dict(call='verdicts', verdicts=[reply])] + [contract_reply()])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 3


def test_bare_bracket_evidence_passes(workspace, monkeypatch):
    path = Path('kb/temenos.md')
    path.write_text(path.read_text() + '\n- [Mother](../../characters/throne/mother.md) – Co-leader and administrator')
    reply = verdict() | dict(evidence='[Mother] – Co-leader and administrator')
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[claim(1, 'canon_fact')]),
                                   dict(call='verdicts', verdicts=[reply])] + [contract_reply()])
    result = run_story()
    assert len(calls) == 3
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
                                   dict(call='verdicts', verdicts=[reply])] + [contract_reply()])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 3


@pytest.mark.parametrize('source', ['kb/temenos.md', 'cards/temenos.md', 'prompts/world_premise.md'])
def test_normalized_evidence_passes(workspace, monkeypatch, source):
    Path(source).write_text(Path(source).read_text() + '\nHe met [his colleague](../people/colleague.md)\n  before the journey.')
    reply = verdict(file=source) | dict(evidence='He met his colleague   before\nthe journey.')
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=[claim(1, 'canon_fact')]),
                                   dict(call='verdicts', verdicts=[reply])] + [contract_reply()])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 3


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
                                   dict(call='verdicts', verdicts=[verdict()])] + [contract_reply()])
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
    ] + [contract_reply()])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 4
    assert len(options) == 2 and life == ['enter', 'exit', 'enter', 'exit']
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
    ] + [contract_reply()])
    result = run_story()
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(calls) == (4 + int(recover))
    assert 'Reply validation failed for verdicts' in calls[3]
    run = next(Path('runs').iterdir())
    assert (run / 'validation.json').exists() == recover


def test_all_evidence_failures_collected(workspace, monkeypatch):
    claims = [claim(1, 'canon_fact'), claim(1, 'canon_fact')]
    invalid = [verdict(i) | dict(evidence='Absent evidence.') for i in range(2)]
    calls, _, _ = fake(monkeypatch, [dict(call='extract', claims=claims),
                                   dict(call='verdicts', verdicts=invalid),
                                   dict(call='verdicts', verdicts=invalid)] + [contract_reply()])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 4
    request = json.loads(calls[2])
    assert request['claims'] == [dict(claim_id=i, **c) for i, c in enumerate(claims)]
    assert [error['claim_id'] for error in request['errors']] == [0, 1]
    run = next(Path('runs').iterdir())
    report = json.loads((run / 'validation.json').read_text())['rounds'][0]
    assert len(report['unverified']) == 2
    events = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert [row['claim_id'] for row in events if row['type'] == 'evidence_check_failed'] == [0, 1, 0, 1]


@pytest.fixture
def log_world(workspace):
    from story_engine.world.models import Event, SceneRecord

    directory = Path('worlds/tiny')
    directory.mkdir(parents=True)
    events = [Event(id=i, day=1, part='morning', place='cropdale', actor='temenos',
                    type='action', content=f'Action {i}.', perceived_by=['temenos'],
                    scene='chosen' if i in (2, 3) else 'other' if i == 4 else None,
                    round=None) for i in range(1, 5)]
    scene = SceneRecord(id='chosen', day=1, part='morning', place='cropdale',
                        participants=['temenos'], first_event_id=2, last_event_id=3,
                        rounds=0, end='done')
    (directory / 'events.jsonl').write_text(''.join(e.model_dump_json() + '\n' for e in events))
    (directory / 'scenes.jsonl').write_text(scene.model_dump_json() + '\n')
    Path('input.md').write_text('Temenos waited.\n\n“Hello,” he said.\nNo entities here.')
    return events


def log_entry(**changes):
    return dict(quote='No entities here.', actor='temenos', events=[2],
                reason='Same action.', verdict='supported') | changes


def log_reply(*entries, paragraph=2):
    count = len([p for p in Path('input.md').read_text().strip().split('\n\n') if p.strip()])
    return dict(call='log', paragraphs=[
        dict(id=i, lines=list(entries) if i == paragraph else []) for i in range(1, count + 1)])


def log_replies(entry):
    return [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[]),
            log_reply(entry, paragraph=1 if '\n\n' not in Path('input.md').read_text() else 2)]


def run_log(*options):
    return CliRunner().invoke(app, ['eval', 'validate', 'input.md',
                                  *(options or ('--world', 'tiny', '--scene', 'chosen'))])


def test_log_input_and_legacy_rounds(log_world, monkeypatch):
    from story_engine.agents.narrator import act_beats, act_scene_events

    calls, options, life = fake(monkeypatch, log_replies(log_entry(events=[1, 2, 3])) + [contract_reply()])
    result = run_log()
    assert result.exit_code == 0, result.output
    assert len(calls) == 4 and len(options) == 2 and life == ['enter', 'exit', 'enter', 'exit']
    request = json.loads(calls[2])
    assert request == dict(call='log', paragraphs=[dict(id=1, text='Temenos waited.'),
                          dict(id=2, text='“Hello,” he said.\nNo entities here.')], scene='chosen',
                          beats=act_beats(act_scene_events(log_world, 'chosen'), pov=''),
                          transition_events=[log_world[0].model_dump(exclude={'intent'})])
    assert len(request['beats']) == 1
    assert 'located' not in options[0].output_format['schema']['$defs']['LogCheck']['properties']
    assert request['beats'][0]['round'] is None
    assert [e['id'] for e in request['beats'][0]['events']] == [2, 3]
    assert Path('prompts/validator_log.md').read_text() in options[0].system_prompt
    assert json.loads(calls[3])['call'] == 'contract'
    assert json.loads(calls[3])['paragraphs'] == request['paragraphs']
    assert 'log_contradicted=0' in result.output


@pytest.mark.parametrize('entry,error', [
    (log_entry(events=[4]), "outside this act's log"),
    (log_entry(events=[]), 'requires at least one event'),
])
@pytest.mark.parametrize('recover', [False, True])
def test_log_whole_reply_retry(log_world, monkeypatch, entry, error, recover):
    replies = log_replies(entry) + [log_reply(log_entry() if recover else entry)]
    calls, options, life = fake(monkeypatch, replies + [contract_reply()])
    result = run_log()
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(calls) == (4 + int(recover)) and error in calls[3]
    assert len(options) == 1 + int(recover)
    assert life == ['enter', 'exit'] * (1 + int(recover))
    run = next(Path('runs').iterdir())
    assert (run / 'validation.json').exists() == recover
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    invalid = [row for row in trace if row['type'] == 'reply_invalid']
    assert [row['attempt'] for row in invalid] == ([1] if recover else [1, 2])
    assert all(row['stage'] == 'log' and error in row['error'] for row in invalid)
    if not recover:
        assert 'after one retry' in result.output
        assert json.loads((run / 'meta.json').read_text())['status'] == 'failed'


def test_log_contradiction_count_scene_and_print(log_world, monkeypatch):
    entry = log_entry(verdict='contradicted', events=[])
    calls, _, _ = fake(monkeypatch, log_replies(entry) + [contract_reply()])
    result = run_log()
    assert result.exit_code == 0, result.output
    assert len(calls) == 4
    assert 'contradicted=1' in result.output
    assert 'log_contradicted=1' in result.output
    assert 'No entities here. [scene chosen]' in result.output
    run = next(Path('runs').iterdir())
    report = Validation.model_validate_json((run / 'validation.json').read_text()).rounds[0]
    assert report.contradicted == 1
    assert report.log[0].model_dump() == entry | dict(scene='chosen', located=True, paragraph=2)


@pytest.mark.parametrize('args,message', [
    (('--world', 'tiny'), 'provided together'),
    (('--scene', 'chosen'), 'provided together'),
    (('--world', 'missing', '--scene', 'chosen'), 'Unknown world: missing'),
    (('--world', 'tiny', '--scene', 'missing'), 'Unknown scene: missing'),
])
def test_log_invalid_context_before_model(log_world, monkeypatch, args, message):
    calls, options, _ = fake(monkeypatch, [])
    result = run_log(*args)
    assert result.exit_code == 1 and message in result.output
    assert calls == options == []


def test_no_log_prompt_and_null(workspace, monkeypatch):
    calls, options, _ = fake(monkeypatch, [dict(call='extract', claims=[]),
                                         dict(call='verdicts', verdicts=[])] + [contract_reply()])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(calls) == 3
    assert options[0].system_prompt == (Path('prompts/validator_extract.md').read_text()
                                        + '\n' + Path('prompts/validator_verdict.md').read_text())
    run = next(Path('runs').iterdir())
    assert json.loads((run / 'validation.json').read_text())['rounds'][0]['log'] is None


def test_log_quote_normalization(log_world, monkeypatch):
    calls, _, _ = fake(monkeypatch, log_replies(log_entry(quote='"Hello," he said.')) + [contract_reply()])
    result = run_log()
    assert result.exit_code == 0, result.output
    assert len(calls) == 4


def test_log_retry_collects_all_problems(log_world, monkeypatch):
    first = 'First missing quote ' + 'a' * 70
    second = 'Second missing quote ' + 'b' * 70
    bad = log_reply(log_entry(quote=first, events=[999]),
                    log_entry(quote=second, events=[]))
    calls, _, _ = fake(monkeypatch, log_replies(log_entry())[:2]
                        + [bad, log_reply(log_entry())] + [contract_reply()])
    result = run_log()
    assert result.exit_code == 0, result.output
    assert len(calls) == 5
    retry = calls[3]
    assert f"event ids outside this act's log: {first[:60]!r}: [999]" in retry
    assert 'log quote not found' not in retry
    assert f'supported log entry requires at least one event: {second[:60]!r}' in retry
    assert first not in retry and second not in retry


@pytest.mark.parametrize('ellipsis', ['…', '...'])
def test_log_interrupted_quote_located(log_world, monkeypatch, ellipsis):
    Path('input.md').write_text('"And second," Gus continued, "I was sorting"')
    entry = log_entry(quote=f'And second, {ellipsis} I was sorting')
    calls, _, _ = fake(monkeypatch, log_replies(entry) + [contract_reply()])
    result = run_log()
    assert result.exit_code == 0, result.output
    assert len(calls) == 4
    run = next(Path('runs').iterdir())
    report = json.loads((run / 'validation.json').read_text())['rounds'][0]
    assert report['log'][0] == entry | dict(scene=None, located=True, paragraph=1)
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert not any(row['type'] in ('reply_invalid', 'log_quote_not_found') for row in trace)


@pytest.mark.parametrize('quote', ['Absent quote.', '', '… ...', 'No entities here. … Absent.'])
@pytest.mark.parametrize('verdict', ['supported', 'contradicted'])
def test_missing_log_quote_kept(log_world, monkeypatch, quote, verdict):
    entry = log_entry(quote=quote, verdict=verdict)
    calls, _, _ = fake(monkeypatch, log_replies(entry) + [contract_reply()])
    result = run_log()
    assert result.exit_code == 0, result.output
    assert len(calls) == 4
    run = next(Path('runs').iterdir())
    assert json.loads((run / 'meta.json').read_text())['status'] == 'passed'
    report = json.loads((run / 'validation.json').read_text())['rounds'][0]
    assert report['log'][0] == entry | dict(
        scene='chosen' if verdict == 'contradicted' else None, located=False, paragraph=2)
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    missing = [row for row in trace if row['type'] == 'log_quote_not_found']
    assert len(missing) == 1
    assert missing[0]['quote'] == quote and missing[0]['verdict'] == verdict
    assert not any(row['type'] == 'reply_invalid' for row in trace)


def test_log_transition_events_exclude_intent(log_world, monkeypatch):
    log_world[0].intent = 'Private transition intent.'
    directory = Path('worlds/tiny')
    (directory / 'events.jsonl').write_text(
        ''.join(event.model_dump_json() + '\n' for event in log_world))
    calls, _, _ = fake(monkeypatch, log_replies(log_entry()) + [contract_reply()])
    result = run_log()
    assert result.exit_code == 0, result.output
    transitions = json.loads(calls[2])['transition_events']
    assert [event['id'] for event in transitions] == [1]
    assert all('intent' not in event for event in transitions)


def test_log_request_marker_free_blank_line_paragraphs(log_world, monkeypatch):
    Path('input.md').write_text('\n<!-- r:1 -->\n\nFirst line.\nStill first.<!-- e:1 -->\n \t\n\nSecond.\n\n<!-- r:2 -->\n')
    reply = dict(call='log', paragraphs=[dict(id=1, lines=[]), dict(id=2, lines=[])])
    calls, _, _ = fake(monkeypatch, log_replies(log_entry())[:2] + [reply] + [contract_reply()])
    result = run_log()
    assert result.exit_code == 0, result.output
    request = json.loads(calls[2])
    assert 'text' not in request
    assert request['paragraphs'] == [dict(id=1, text='First line.\nStill first.'),
                                     dict(id=2, text='Second.')]
    assert json.loads(calls[3])['paragraphs'] == request['paragraphs']


@pytest.mark.parametrize('recover', [False, True])
def test_log_missing_paragraph_retries(log_world, monkeypatch, recover):
    bad = dict(call='log', paragraphs=[dict(id=1, lines=[])])
    calls, _, _ = fake(monkeypatch, log_replies(log_entry())[:2] + [
        bad, log_reply(log_entry()) if recover else bad] + [contract_reply()])
    result = run_log()
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(calls) == (4 + int(recover))
    assert 'missing paragraph ids: [2]' in calls[3]
    if not recover:
        assert 'after one retry' in result.output
        assert 'missing paragraph ids: [2]' in result.output


def test_log_paragraph_and_event_problems_collected(log_world, monkeypatch):
    bad = dict(call='log', paragraphs=[dict(id=1, lines=[log_entry(events=[999]),
                                                         log_entry(events=[])]),
                                       dict(id=1, lines=[]), dict(id=9, lines=[])])
    calls, _, _ = fake(monkeypatch, log_replies(log_entry())[:2] + [bad, bad])
    assert run_log().exit_code == 1
    assert len(calls) == 4
    for error in ('missing paragraph ids: [2]', 'duplicate paragraph ids: [1]',
                  'unknown paragraph ids: [9]', "event ids outside this act's log",
                  'supported log entry requires at least one event'):
        assert error in calls[3]


@pytest.mark.parametrize('paragraph,located', [(1, True), (2, False)])
def test_log_quote_location_is_paragraph_local(log_world, monkeypatch, paragraph, located):
    entry = log_entry(quote='Temenos waited.')
    calls, _, _ = fake(monkeypatch, log_replies(entry)[:2] + [
        log_reply(entry, paragraph=paragraph)] + [contract_reply()])
    result = run_log()
    assert result.exit_code == 0, result.output
    assert len(calls) == 4
    run = next(Path('runs').iterdir())
    report = json.loads((run / 'validation.json').read_text())['rounds'][0]
    assert report['log'] == [entry | dict(paragraph=paragraph, located=located, scene=None)]
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert sum(row['type'] == 'log_quote_not_found' for row in trace) == int(not located)


def contract_finding(**changes):
    return dict(paragraph=2, quote='No entities here.', kind='pov',
                reason='Uninspected contract reason.') | changes


@pytest.mark.parametrize('with_log', [False, True])
def test_contract_uses_fresh_client_after_validator_closes(log_world, monkeypatch, with_log):
    from claude_agent_sdk import ResultMessage
    from story_engine.agents import validation
    from story_engine.agents.sdk import json_schema_output

    replies = iter(log_replies(log_entry())[:3 if with_log else 2] + [contract_reply()])
    clients, life = [], []

    class Client:
        def __init__(self, *, options):
            self.options = options
            self.calls = []
            self.id = len(clients)
            life.append(('create', self.id))
            clients.append(self)

        async def __aenter__(self):
            life.append(('enter', self.id))
            return self

        async def __aexit__(self, *args):
            life.append(('exit', self.id))

        async def query(self, request):
            self.calls.append(json.loads(request))

        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake',
                                structured_output=next(replies), total_cost_usd=.1 * len(self.calls))

    monkeypatch.setattr(validation, 'ClaudeSDKClient', Client)
    result = run_log() if with_log else run_story()
    assert result.exit_code == 0, result.output
    assert life == [('create', 0), ('enter', 0), ('exit', 0),
                    ('create', 1), ('enter', 1), ('exit', 1)]
    validator, contract = clients
    assert [call['call'] for call in validator.calls] == ['extract', 'verdicts'] + (['log'] if with_log else [])
    assert [call['call'] for call in contract.calls] == ['contract']
    contract_prompt = Path('prompts/validator_contract.md').read_text()
    extract_prompt = Path('prompts/validator_extract.md').read_text()
    assert contract.options.system_prompt == contract_prompt
    assert extract_prompt not in contract.options.system_prompt
    assert extract_prompt in validator.options.system_prompt
    assert contract_prompt not in validator.options.system_prompt
    schema = validator.options.output_format['schema']
    assert 'ContractReply' not in schema['$defs']
    assert {variant['$ref'].split('/')[-1] for variant in schema['properties']['reply']['anyOf']} == (
        {'ExtractReply', 'VerdictReply'} | ({'LogReply'} if with_log else set()))
    assert contract.options.output_format == json_schema_output(validation.ContractReply)
    request = contract.calls[0]
    assert request['style_specification'] == Path('prompts/style_spec.md').read_text()
    if with_log:
        assert request['paragraphs'] == validator.calls[2]['paragraphs']
    directory = next(Path('runs').iterdir())
    trace = [json.loads(line) for line in (directory / 'trace.jsonl').read_text().splitlines()]
    usage = [row for row in trace if row['type'] == 'stage_usage']
    assert [row['agent'] for row in usage] == ['validator'] * len(validator.calls) + ['validator_contract']
    assert all(row['call_cost_usd'] == pytest.approx(.1) for row in usage)


@pytest.mark.parametrize('kind', ['pov', 'meta', 'left_open', 'scope'])
def test_contract_finding_stored_counted_and_fixed(workspace, monkeypatch, kind):
    from story_engine.agents.narrator import _fix_items

    finding = contract_finding(kind=kind)
    calls, options, life = fake(monkeypatch, [
        dict(call='extract', claims=[claim(1, 'canon_fact')]),
        dict(call='verdicts', verdicts=[verdict()]),
        dict(call='contract', findings=[finding]),
    ])
    result = run_story()
    assert result.exit_code == 0, result.output
    assert len(options) == 2 and life == ['enter', 'exit', 'enter', 'exit']
    assert [json.loads(call)['call'] for call in calls] == ['extract', 'verdicts', 'contract']
    request = json.loads(calls[2])
    assert not Path('docs').exists()
    assert request == dict(
        call='contract', paragraphs=[dict(id=1, text='Temenos made an assertion.'),
                                    dict(id=2, text='No entities here.')],
        style_specification=Path('prompts/style_spec.md').read_text(encoding='utf-8'),
    )
    assert options[1].system_prompt == Path('prompts/validator_contract.md').read_text()
    schema = options[1].output_format['schema']
    assert schema['properties']['call']['const'] == 'contract'
    assert 'located' not in schema['$defs']['ContractFinding']['properties']
    directory = next(Path('runs').iterdir())
    report = Validation.model_validate_json((directory / 'validation.json').read_text()).rounds[0]
    assert [entry.model_dump() for entry in report.contract] == [finding | dict(located=True)]
    assert report.contradicted == 2  # One canon contradiction plus one contract finding.
    assert _fix_items(report)[-1] == dict(id=2, **finding)


@pytest.mark.parametrize('recover', [False, True])
def test_contract_unknown_paragraph_retries(workspace, monkeypatch, recover):
    bad = dict(call='contract', findings=[contract_finding(paragraph=99)])
    calls, options, life = fake(monkeypatch, [
        dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[]),
        bad, dict(call='contract', findings=[contract_finding()]) if recover else bad,
    ])
    result = run_story()
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(calls) == 4 and 'unknown paragraph ids: [99]' in calls[3]
    assert 'Reply validation failed for contract' in calls[3]
    assert len(options) == 2 and life == ['enter', 'exit', 'enter', 'exit']
    directory = next(Path('runs').iterdir())
    assert (directory / 'validation.json').exists() == recover
    trace = [json.loads(line) for line in (directory / 'trace.jsonl').read_text().splitlines()]
    invalid = [row for row in trace if row['type'] == 'reply_invalid']
    assert [row['attempt'] for row in invalid] == ([1] if recover else [1, 2])
    assert all(row['stage'] == 'contract' for row in invalid)
    if not recover:
        assert 'after one retry' in result.output
    else:
        report = Validation.model_validate_json((directory / 'validation.json').read_text()).rounds[0]
        assert report.contract[0].paragraph == 2 and report.contradicted == 1


@pytest.mark.parametrize('quote,located', [
    ('Absent quote.', False), ('Temenos made an assertion.', False),
    ('', False), ('… ...', False), ('No entities here. … Absent.', False),
    ('No entities … here.', True), ('No entities ... here.', True),
])
def test_contract_quote_location_is_paragraph_local(workspace, monkeypatch, quote, located):
    from story_engine.agents.narrator import _fix_items

    finding = contract_finding(quote=quote)
    calls, _, _ = fake(monkeypatch, [
        dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[]),
        dict(call='contract', findings=[finding]),
    ])
    assert run_story().exit_code == 0
    assert len(calls) == 3  # A missing quote is kept without a retry.
    directory = next(Path('runs').iterdir())
    report = Validation.model_validate_json((directory / 'validation.json').read_text()).rounds[0]
    assert report.contract[0].model_dump() == finding | dict(located=located)
    assert report.contradicted == 1 and _fix_items(report) == [dict(id=1, **finding)]
    trace = [json.loads(line) for line in (directory / 'trace.jsonl').read_text().splitlines()]
    missing = [row for row in trace if row['type'] == 'contract_quote_not_found']
    assert len(missing) == int(not located)
    if missing:
        assert all(missing[0][key] == value for key, value in finding.items())
    assert not any(row['type'] == 'reply_invalid' for row in trace)


@pytest.mark.parametrize('kind,count', [('supported', 0), ('contradicted', 1)])
def test_empty_contract_keeps_contradicted_count(workspace, monkeypatch, kind, count):
    calls, _, _ = fake(monkeypatch, [
        dict(call='extract', claims=[claim(1, 'canon_fact')]),
        dict(call='verdicts', verdicts=[verdict(kind=kind)]),
        contract_reply(),
    ])
    assert run_story().exit_code == 0
    assert len(calls) == 3
    directory = next(Path('runs').iterdir())
    report = Validation.model_validate_json((directory / 'validation.json').read_text()).rounds[0]
    assert report.contract == [] and report.contradicted == count
