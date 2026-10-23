"""Evaluate claim types on the fixed validator test set."""

import json
from pathlib import Path

from story_engine.agents.sdk import SessionCost, SessionError
from story_engine.agents.validation import Claim, Claims, ClaimType, extract_claims
from story_engine.config import StrictModel, load_configs
from story_engine.kb.entities import EntitySentence, entity_dictionary, prefilter
from story_engine.runs import create_run, finish_run
from story_engine.trace import TraceWriter


class SentenceScore(StrictModel):
    sentence_id: int
    expected_type: ClaimType
    predicted_types: list[ClaimType]
    correct: bool


class ExtractScore(StrictModel):
    sentences: list[SentenceScore]
    type_accuracy: float
    cost_usd: float = 0.0
    error: str | None = None


def score_claims(rows: list[dict], claims: list[Claim]) -> ExtractScore:
    scores = []
    for row in rows:
        types = sorted({c.type for c in claims if c.sentence_id == row['id']})
        expected = row['type']
        correct = expected in types and (expected == 'canon_fact' or 'canon_fact' not in types)
        scores.append(SentenceScore(sentence_id=row['id'], expected_type=expected,
                                    predicted_types=types, correct=correct))
    return ExtractScore(sentences=scores,
                        type_accuracy=sum(s.correct for s in scores) / len(scores) if scores else 0.0)


async def evaluate_extract(models_file: str | Path = 'config/models.yaml'):
    models, settings = load_configs(models_file)
    rows = [json.loads(line) for line in Path('eval/validator_testset.jsonl').read_text().splitlines()
            if line.strip()]
    dictionary = entity_dictionary()
    sentences = [EntitySentence(sentence_id=row['id'], text=row['text'],
                                entities=sorted({e for s in prefilter(row['text'], dictionary)
                                                 for e in s.entities})) for row in rows]
    run_dir = create_run([], '', 'validator test set', 'extract_eval', None, models,
                         status='running', models_file=str(models_file))
    trace = TraceWriter(run_dir)
    trace.write('run_started', mode='extract_eval')
    cost = SessionCost()
    claims = []
    error = None
    try:
        claims = await extract_claims(sentences, root=Path.cwd(), run_dir=run_dir,
                                      role=models.validator, max_turns=settings.agent_max_turns,
                                      trace=trace, cost=cost)
    except Exception as failure:
        error = str(failure) if isinstance(failure, SessionError) else f'{type(failure).__name__}: {failure}'
        trace.write('stage_failed', stage='extract', error=error)
    report = score_claims(rows, claims)
    report.cost_usd, report.error = cost.total, error
    (run_dir / 'claims.json').write_text(Claims(claims=claims).model_dump_json(indent=2), encoding='utf-8')
    (run_dir / 'extract_score.json').write_text(report.model_dump_json(indent=2), encoding='utf-8')
    status = 'failed' if error else 'passed'
    finish_run(run_dir, status, error)
    trace.write('run_finished', status=status)
    return run_dir, report, claims
