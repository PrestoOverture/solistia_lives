"""Structured claim extraction with data-reference checks only."""

import json
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from claude_agent_sdk import ClaudeSDKClient, ResultMessage

from story_engine.agents.sdk import (
    run_call, KBHooks, SessionCost, SessionError, json_schema_output, session_error,
    session_options, structured_reply,
)
from story_engine.config import StrictModel
from story_engine.kb import TRAVELERS
from story_engine.kb.entities import EntitySentence, entity_dictionary
from story_engine.runs import record_api_host

ClaimType = Literal['canon_fact', 'invented_detail', 'opinion_or_joke']


class Claim(StrictModel):
    sentence_id: int
    quote: str
    claim: str
    type: ClaimType
    entities: list[str]


class Claims(StrictModel):
    claims: list[Claim]


class ExtractReply(Claims):
    call: Literal['extract']


class Verdict(StrictModel):
    claim_id: int
    evidence: str
    reason: str
    verdict: Literal['supported', 'contradicted', 'not_in_kb']
    source: str | None


class VerdictReply(StrictModel):
    call: Literal['verdicts']
    verdicts: list[Verdict]


ValidatorReply = Annotated[ExtractReply | VerdictReply, Field(discriminator='call')]


class CheckedClaim(Claim):
    evidence: str
    reason: str
    verdict: Literal['supported', 'contradicted', 'not_in_kb']
    source: str | None


class ValidationRound(StrictModel):
    round: int
    claims: list[CheckedClaim | Claim]
    not_in_kb: list[CheckedClaim]
    contradicted: int


class Validation(StrictModel):
    rounds: list[ValidationRound]


def _check_claims(claims, sentences, root):
    allowed_ids = {sentence.sentence_id for sentence in sentences}
    unknown = {c.sentence_id for c in claims} - allowed_ids
    if unknown:
        raise ValueError(f'unknown sentence_id: {sorted(unknown)}')
    allowed_entities = set().union(*entity_dictionary(root / 'kb').values())
    unknown_entities = {e for c in claims for e in c.entities} - allowed_entities
    if unknown_entities:
        raise ValueError(f'unknown entity slugs: {sorted(unknown_entities)}')


async def _call(client, request, *, parse, check, hooks, trace, cost, options, stage, role):
    for attempt in range(role.retries + 1):
        async def receive_call():
            await client.query(request)
            result = structured = None
            async for message in client.receive_response():
                hooks.observe(message)
                if isinstance(message, ResultMessage):
                    trace.write('stage_usage', stage=stage, agent='validator',
                                attempt=attempt + 1, usage=message.usage or {},
                                num_turns=message.num_turns, total_cost_usd=message.total_cost_usd,
                                call_cost_usd=cost.delta(message.total_cost_usd))
                    if message.is_error or message.subtype != 'success':
                        raise session_error(f'Validator {message.subtype}: '
                                            + ('; '.join(message.errors or []) or message.result or 'SDK error'), options.env)
                    result, structured = message.result, message.structured_output
            return result, structured
        result, structured = await run_call(receive_call(), role=role, trace=trace, stage=stage, agent="validator")
        try:
            reply = parse(structured_reply(result, structured))
            check(reply)
            return reply
        except ValueError as error:
            if attempt == role.retries:
                raise SessionError(f'{stage} validation failed after {"one retry" if role.retries == 1 else str(role.retries) + " retries"}: {error}') from None
            request = f'Reply validation failed for {stage}: {error}\nReturn corrected structured output.'
    raise AssertionError('unreachable')


def _options(root, run_dir, role, max_turns, schema, verdicts=False):
    hooks = KBHooks(root, run_dir, 'validator', 1)
    prompt = (root / 'prompts/validator_extract.md').read_text()
    if verdicts:
        prompt += '\n' + (root / 'prompts/validator_verdict.md').read_text()
    options = session_options(root, run_dir, role, prompt, max_turns, hooks,
                              tools=['Read', 'Grep'], output_format=json_schema_output(schema))
    record_api_host(run_dir, options.env.get('ANTHROPIC_BASE_URL'))
    return hooks, options


async def extract_claims(sentences: list[EntitySentence], *, root: Path, run_dir: Path,
                         role, max_turns: int, trace, cost: SessionCost) -> list[Claim]:
    if any(s.sentence_id is None for s in sentences):
        raise ValueError('extraction inputs require sentence_id')
    hooks, options = _options(root, run_dir, role, max_turns, Claims)
    request = json.dumps({'sentences': [s.model_dump() for s in sentences]}, ensure_ascii=False)
    async with ClaudeSDKClient(options=options) as client:
        reply = await _call(client, request, parse=Claims.model_validate,
                            check=lambda r: _check_claims(r.claims, sentences, root),
                            hooks=hooks, trace=trace, cost=cost, options=options, stage='extract', role=role)
    return reply.claims


def _check_verdicts(reply, claims, root, trace):
    if not isinstance(reply, VerdictReply):
        raise ValueError('expected call: verdicts')
    expected = {i for i, c in enumerate(claims) if c.type == 'canon_fact'}
    ids = [v.claim_id for v in reply.verdicts]
    if set(ids) != expected or len(ids) != len(expected):
        raise ValueError(f'exactly one verdict required for each canon_fact claim: {sorted(expected)}; got {ids}')
    root = root.resolve()
    card_sources = {f'cards/{slug}.md' for slug in TRAVELERS}
    for verdict in reply.verdicts:
        if verdict.source is None:
            if verdict.verdict in ('supported', 'contradicted'):
                raise ValueError('supported and contradicted require a source')
            if verdict.evidence.strip():
                raise ValueError('evidence requires a source')
            continue
        raw = Path(verdict.source)
        path = (root / raw).resolve()
        allowed = (raw.parts[:1] == ('kb',) and path.is_relative_to(root / 'kb')
                   or verdict.source in card_sources | {'prompts/world_premise.md'}
                   and path == root / raw)
        if raw.is_absolute() or '..' in raw.parts or not allowed or not path.is_file():
            raise ValueError(f'source must name an existing repo-relative file under kb/, '
                             f'cards/<traveler>.md, or prompts/world_premise.md: {verdict.source}')
        fragments = [_normalize_evidence(part) for part in re.split(r'…|\.{3}', verdict.evidence)]
        fragments = [part for part in fragments if part]
        source = _normalize_evidence(path.read_text(encoding='utf-8'))
        if not fragments or any(part not in source for part in fragments):
            trace.write('evidence_check_failed', claim_id=verdict.claim_id,
                        source=verdict.source, evidence=verdict.evidence)
            raise ValueError(f'evidence does not appear in source: {verdict.source}')


def _normalize_evidence(text):
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = text.translate(str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'"}))
    text = re.sub(r'(?m)^[ \t]*(?:#{1,6}|[-*]|\d+\.)[ \t]+', '', text)
    # Remove paired emphasis, preserving literal markers such as snake_case.
    for marker in (r'\*\*', r'\*', '_'):
        text = re.sub(rf'(?<!\w){marker}(?=\S)(.+?)(?<=\S){marker}(?!\w)',
                      r'\1', text, flags=re.DOTALL)
    return ' '.join(text.split())


async def validate_text(text: str, *, root: Path, run_dir: Path, role, max_turns: int,
                        trace, cost: SessionCost) -> Validation:
    from story_engine.kb.entities import prefilter

    sentences = prefilter(text, entity_dictionary(root / 'kb'))
    for i, sentence in enumerate(sentences, 1):
        sentence.sentence_id = i
    hooks, options = _options(root, run_dir, role, max_turns, ValidatorReply, verdicts=True)

    def check_extract(reply):
        if not isinstance(reply, ExtractReply):
            raise ValueError('expected call: extract')
        _check_claims(reply.claims, sentences, root)

    async with ClaudeSDKClient(options=options) as client:
        common = dict(role=role, hooks=hooks, trace=trace, cost=cost, options=options,
                      parse=TypeAdapter(ValidatorReply).validate_python)
        extracted = await _call(client, json.dumps({'call': 'extract', 'sentences': [
            s.model_dump() for s in sentences]}, ensure_ascii=False),
            check=check_extract, stage='extract', **common)
        claims = extracted.claims
        hooks.turn = 2
        sources = {'prompts/world_premise.md': (root / 'prompts/world_premise.md').read_text()}
        for slug in sorted({e for c in claims for e in c.entities} & TRAVELERS):
            name = f'cards/{slug}.md'
            sources[name] = (root / name).read_text()
        verdicts = await _call(client, json.dumps({'call': 'verdicts', 'sources': sources, 'claims': [
            dict(claim_id=i, **c.model_dump()) for i, c in enumerate(claims)
            if c.type == 'canon_fact']}, ensure_ascii=False),
            check=lambda r: _check_verdicts(r, claims, root, trace), stage='verdicts', **common)
    by_id = {v.claim_id: v for v in verdicts.verdicts}
    checked = [CheckedClaim(**c.model_dump(), **by_id[i].model_dump(exclude={'claim_id'}))
               if i in by_id else c for i, c in enumerate(claims)]
    report = Validation(rounds=[ValidationRound(
        round=1, claims=checked,
        not_in_kb=[c for c in checked if isinstance(c, CheckedClaim) and c.verdict == 'not_in_kb'],
        contradicted=sum(v.verdict == 'contradicted' for v in verdicts.verdicts),
    )])
    (run_dir / 'validation.json').write_text(report.model_dump_json(indent=2), encoding='utf-8')
    return report
