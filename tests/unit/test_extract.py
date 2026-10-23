import json
import shutil
from pathlib import Path

import pytest
import yaml
from claude_agent_sdk import ResultMessage
from pydantic import ValidationError
from typer.testing import CliRunner

from story_engine.agents import validation
from story_engine.agents.validation import Claim
from story_engine.cli import app
from story_engine.eval.extract import score_claims

ROOT = Path(__file__).resolve().parents[2]


def claim(sentence_id=17, type='opinion_or_joke', entities=None):
    return dict(sentence_id=sentence_id, quote='Uninspected quote.', claim='Uninspected assertion.',
                type=type, entities=['temenos'] if entities is None else entities)


@pytest.mark.parametrize('change', [dict(type='supported'), dict(sentence_id=[]),
                                  dict(entities='temenos'), dict(quote=None), dict(extra=True)])
def test_claim_schema(change):
    with pytest.raises(ValidationError):
        Claim.model_validate(claim() | change)


def test_claim_fields_required_and_types():
    for key in claim():
        data = claim()
        del data[key]
        with pytest.raises(ValidationError):
            Claim.model_validate(data)
    for kind in ('canon_fact', 'invented_detail', 'opinion_or_joke'):
        assert Claim.model_validate(claim(type=kind)).type == kind


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    for name in ('config', 'prompts'):
        shutil.copytree(ROOT / name, tmp_path / name)
    (tmp_path / 'eval').mkdir()
    shutil.copy(ROOT / 'eval/validator_testset.jsonl', tmp_path / 'eval')
    shutil.copy(ROOT / 'eval/e3_validator_adaptive.yaml', tmp_path / 'eval')
    (tmp_path / 'kb').mkdir()
    (tmp_path / 'kb/temenos.md').write_text('---\nname: Temenos\naliases: []\n---\n')
    monkeypatch.chdir(tmp_path)


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
            yield ResultMessage('success', 1, 1, False, 1, 'fake',
                                structured_output=next(replies), total_cost_usd=.1 * len(calls))

    monkeypatch.setattr(validation, 'ClaudeSDKClient', Client)
    return calls, options, life


@pytest.mark.parametrize('bad,error', [
    (claim(sentence_id=999), 'unknown sentence_id: [999]'),
    (claim(entities=['non_kb_slug']), "unknown entity slugs: ['non_kb_slug']"),
])
@pytest.mark.parametrize('recover', [False, True])
def test_retry_and_failed_run(workspace, monkeypatch, bad, error, recover):
    calls, options, life = fake(monkeypatch, [dict(claims=[bad]),
                                            dict(claims=[claim()] if recover else [bad])])
    result = CliRunner().invoke(app, ['eval', 'extract'])
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(calls) == 2 and error in calls[1]
    assert len(options) == 1 and life == ['enter', 'exit']
    run = next(Path('runs').iterdir())
    meta = json.loads((run / 'meta.json').read_text())
    assert meta['status'] == ('passed' if recover else 'failed')
    report = json.loads((run / 'extract_score.json').read_text())
    assert report['cost_usd'] == .2
    if not recover:
        assert error in report['error'] and 'after one retry' in report['error']
        assert json.loads((run / 'claims.json').read_text()) == {'claims': []}
    usage = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert len([row for row in usage if row['type'] == 'stage_usage']) == 2


def test_scoring():
    rows = [dict(id=i, type=kind) for i, kind in enumerate(
        ['canon_fact', 'invented_detail', 'opinion_or_joke', 'canon_fact', 'opinion_or_joke',
         'invented_detail'], 1)]
    claims = [claim(1, 'canon_fact'), claim(1, 'opinion_or_joke'),
              claim(2, 'invented_detail'), claim(3, 'opinion_or_joke'),
              claim(5, 'opinion_or_joke'), claim(5, 'canon_fact'),
              claim(6, 'invented_detail'), claim(6, 'canon_fact')]
    score = score_claims(rows, [Claim(**c) for c in claims])
    assert [s.correct for s in score.sentences] == [True, True, True, False, False, False]
    assert score.sentences[3].predicted_types == []
    assert score.type_accuracy == .5


def test_cli_artifacts_and_session(workspace, monkeypatch):
    calls, options, life = fake(monkeypatch, [dict(claims=[claim()])])
    result = CliRunner().invoke(app, ['eval', 'extract', '--models', 'eval/e3_validator_adaptive.yaml'])
    assert result.exit_code == 0, result.output
    assert 'type accuracy=3.85%' in result.output and 'Item 17:' in result.output
    assert 'Uninspected assertion.' in result.output
    run = next(Path('runs').iterdir())
    assert json.loads((run / 'claims.json').read_text()) == dict(claims=[claim()])
    report = json.loads((run / 'extract_score.json').read_text())
    assert len(report['sentences']) == 26 and report['sentences'][16]['correct']
    payload = json.loads(calls[0])['sentences']
    assert [s['sentence_id'] for s in payload] == list(range(1, 27))
    assert payload[16]['entities'] == ['temenos']
    assert options[0].tools == options[0].allowed_tools == ['Read', 'Grep']
    assert options[0].output_format['type'] == 'json_schema'
    assert options[0].thinking == {'type': 'adaptive'}
    assert options[0].system_prompt == Path('prompts/validator_extract.md').read_text()
    assert life == ['enter', 'exit']
    meta = json.loads((run / 'meta.json').read_text())
    assert meta['models_file'] == 'eval/e3_validator_adaptive.yaml'
    assert meta['status'] == 'passed'
    assert (run / 'retrieval.jsonl').exists()


def test_adaptive_config_only_changes_validator_thinking():
    original = yaml.safe_load((ROOT / 'config/models.yaml').read_text())
    adaptive = yaml.safe_load((ROOT / 'eval/e3_validator_adaptive.yaml').read_text())
    original['validator']['thinking'] = 'adaptive'
    assert original == adaptive


def test_help():
    result = CliRunner().invoke(app, ['eval', 'extract', '--help'], color=False)
    assert result.exit_code == 0
    assert 'extract' in result.output and '--models' in result.output
