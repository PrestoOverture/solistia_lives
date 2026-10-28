"""Structured claim extraction with data-reference checks only."""

import json
from collections import Counter
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from claude_agent_sdk import ClaudeSDKClient, ResultMessage

from story_engine.agents.narrator import strip_markers
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


class LogCheck(StrictModel):
    quote: str
    actor: str
    events: list[int]
    reason: str
    verdict: Literal['supported', 'contradicted']
    scene: str | None = None


class LogParagraph(StrictModel):
    id: int
    lines: list[LogCheck]


class LogReply(StrictModel):
    call: Literal['log']
    paragraphs: list[LogParagraph]


class StoredLogCheck(LogCheck):
    paragraph: int
    located: bool


class ContractFinding(StrictModel):
    paragraph: int
    quote: str
    kind: Literal['pov', 'meta', 'left_open', 'scope']
    reason: str


class ContractReply(StrictModel):
    call: Literal['contract']
    findings: list[ContractFinding]


class StoredContractFinding(ContractFinding):
    located: bool


ValidatorReply = Annotated[ExtractReply | VerdictReply, Field(discriminator='call')]
LogValidatorReply = Annotated[ExtractReply | VerdictReply | LogReply, Field(discriminator='call')]


class CheckedClaim(Claim):
    claimed_verdict: Literal['supported', 'contradicted', 'not_in_kb'] | None = None
    evidence: str
    reason: str
    verdict: Literal['supported', 'contradicted', 'not_in_kb', 'unverified']
    source: str | None


class ValidationRound(StrictModel):
    round: int
    claims: list[CheckedClaim | Claim]
    not_in_kb: list[CheckedClaim]
    contradicted: int
    unverified: list[CheckedClaim]
    log: list[StoredLogCheck] | None = None
    contract: list[StoredContractFinding] = Field(default_factory=list)


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


async def _call(client, request, *, parse, check, hooks, trace, cost, options, stage, role, agent="validator"):
    for attempt in range(role.retries + 1):
        async def receive_call():
            await client.query(request)
            result = structured = None
            async for message in client.receive_response():
                hooks.observe(message)
                if isinstance(message, ResultMessage):
                    trace.write('stage_usage', stage=stage, agent=agent,
                                attempt=attempt + 1, usage=message.usage or {},
                                num_turns=message.num_turns, total_cost_usd=message.total_cost_usd,
                                call_cost_usd=cost.delta(message.total_cost_usd))
                    if message.is_error or message.subtype != 'success':
                        raise session_error(f'Validator {message.subtype}: '
                                            + ('; '.join(message.errors or []) or message.result or 'SDK error'), options.env)
                    result, structured = message.result, message.structured_output
            return result, structured
        result, structured = await run_call(receive_call(), role=role, trace=trace, stage=stage, agent=agent)
        try:
            reply = parse(structured_reply(result, structured))
            check(reply)
            return reply
        except ValueError as error:
            trace.write('reply_invalid', stage=stage, attempt=attempt + 1, error=str(error))
            if attempt == role.retries:
                raise SessionError(f'{stage} validation failed after {"one retry" if role.retries == 1 else str(role.retries) + " retries"}: {error}') from None
            request = f'Reply validation failed for {stage}: {error}\nReturn corrected structured output.'
    raise AssertionError('unreachable')


def _options(root, run_dir, role, max_turns, schema, verdicts=False, log=False):
    hooks = KBHooks(root, run_dir, 'validator', 1)
    prompt = (root / 'prompts/validator_extract.md').read_text()
    if verdicts:
        prompt += '\n' + (root / 'prompts/validator_verdict.md').read_text()
    if log:
        prompt += '\n' + (root / 'prompts/validator_log.md').read_text()
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


def _check_verdicts(reply, expected, root):
    if not isinstance(reply, VerdictReply):
        raise ValueError('expected call: verdicts')
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


def _evidence_failures(reply, root, trace):
    failed = {}
    for verdict in reply.verdicts:
        if verdict.source is None:
            continue
        path = root / verdict.source
        fragments = [_normalize_evidence(part) for part in re.split(r'…|\.{3}', verdict.evidence)]
        fragments = [part for part in fragments if part]
        source = _normalize_evidence(path.read_text(encoding='utf-8'))
        if not fragments or any(part not in source for part in fragments):
            trace.write('evidence_check_failed', claim_id=verdict.claim_id,
                        source=verdict.source, evidence=verdict.evidence)
            failed[verdict.claim_id] = verdict.source
    return failed


def _normalize_evidence(text):
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\[([^\]]+)\](?!\()', r'\1', text)
    text = text.translate(str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'"}))
    text = re.sub(r'(?m)^[ \t]*(?:#{1,6}|[-*]|\d+\.)[ \t]+', '', text)
    # Remove paired emphasis, preserving literal markers such as snake_case.
    for marker in (r'\*\*', r'\*', '_'):
        text = re.sub(rf'(?<!\w){marker}(?=\S)(.+?)(?<=\S){marker}(?!\w)',
                      r'\1', text, flags=re.DOTALL)
    return ' '.join(text.split())


def _quote_located(quote, paragraph):
    fragments = [_normalize_evidence(part) for part in re.split(r'…|\.{3}', quote)]
    fragments = [part for part in fragments if part]
    return bool(fragments) and all(part in paragraph for part in fragments)


async def validate_text(text: str, *, root: Path, run_dir: Path, role, max_turns: int,
                        trace, cost: SessionCost, log_input: dict | None = None) -> Validation:
    from story_engine.kb.entities import prefilter

    sentences = prefilter(text, entity_dictionary(root / 'kb'))
    for i, sentence in enumerate(sentences, 1):
        sentence.sentence_id = i
    schema = LogValidatorReply if log_input is not None else ValidatorReply
    hooks, options = _options(root, run_dir, role, max_turns, schema, verdicts=True,
                              log=log_input is not None)
    log = None
    paragraphs = [dict(id=i, text=part) for i, part in enumerate(
        (part.strip() for part in re.split(r"\n[ \t]*\n", strip_markers(text)) if part.strip()), 1)]
    paragraph_text = {p['id']: _normalize_evidence(p['text']) for p in paragraphs}

    def check_log(reply):
        if not isinstance(reply, LogReply):
            raise ValueError('expected call: log')
        allowed = {event['id'] for beat in log_input['beats'] for event in beat['events']}
        allowed.update(event['id'] for event in log_input['transition_events'])
        problems = []
        counts = Counter(p.id for p in reply.paragraphs)
        missing = set(paragraph_text) - counts.keys()
        duplicate = {id for id, count in counts.items() if count > 1}
        unknown = counts.keys() - set(paragraph_text)
        for label, ids in (('missing', missing), ('duplicate', duplicate), ('unknown', unknown)):
            if ids:
                problems.append(f'{label} paragraph ids: {sorted(ids)}')
        for entry in (line for p in reply.paragraphs for line in p.lines):
            outside = set(entry.events) - allowed
            if outside:
                problems.append(f"event ids outside this act's log: {entry.quote[:60]!r}: {sorted(outside)}")
            if entry.verdict == 'supported' and not entry.events:
                problems.append(f'supported log entry requires at least one event: {entry.quote[:60]!r}')
        if problems:
            raise ValueError('; '.join(problems))

    def check_extract(reply):
        if not isinstance(reply, ExtractReply):
            raise ValueError('expected call: extract')
        _check_claims(reply.claims, sentences, root)

    def check_contract(reply):
        if not isinstance(reply, ContractReply):
            raise ValueError('expected call: contract')
        unknown = {finding.paragraph for finding in reply.findings} - paragraph_text.keys()
        if unknown:
            raise ValueError(f'unknown paragraph ids: {sorted(unknown)}')

    async with ClaudeSDKClient(options=options) as client:
        common = dict(role=role, hooks=hooks, trace=trace, cost=cost, options=options,
                      parse=TypeAdapter(schema).validate_python)
        extracted = await _call(client, json.dumps({'call': 'extract', 'sentences': [
            s.model_dump() for s in sentences]}, ensure_ascii=False),
            check=check_extract, stage='extract', **common)
        claims = extracted.claims
        hooks.turn = 2
        sources = {'prompts/world_premise.md': (root / 'prompts/world_premise.md').read_text()}
        for slug in sorted({e for c in claims for e in c.entities} & TRAVELERS):
            name = f'cards/{slug}.md'
            sources[name] = (root / name).read_text()
        expected = {i for i, c in enumerate(claims) if c.type == 'canon_fact'}
        verdicts = await _call(client, json.dumps({'call': 'verdicts', 'sources': sources, 'claims': [
            dict(claim_id=i, **c.model_dump()) for i, c in enumerate(claims)
            if c.type == 'canon_fact']}, ensure_ascii=False),
            check=lambda r: _check_verdicts(r, expected, root), stage='verdicts', **common)
        by_id = {v.claim_id: v for v in verdicts.verdicts}
        failed = _evidence_failures(verdicts, root, trace)
        if failed:
            hooks.turn = 3
            retry = await _call(client, json.dumps({
                'call': 'verdicts',
                'claims': [dict(claim_id=i, **claims[i].model_dump()) for i in sorted(failed)],
                'errors': [dict(claim_id=i, source=source,
                                error=f'Evidence was not found in {source}. Return a corrected verdict.')
                           for i, source in sorted(failed.items())],
            }, ensure_ascii=False),
                check=lambda r: _check_verdicts(r, set(failed), root), stage='verdicts', **common)
            by_id.update({v.claim_id: v for v in retry.verdicts})
            failed = _evidence_failures(retry, root, trace)
        if log_input is not None:
            hooks.turn += 1
            reply = await _call(client, json.dumps(dict(call='log', paragraphs=paragraphs, **log_input),
                                                    ensure_ascii=False),
                                check=check_log, stage='log', **common)
            log = []
            for paragraph in reply.paragraphs:
                for entry in paragraph.lines:
                    located = _quote_located(entry.quote, paragraph_text[paragraph.id])
                    if not located:
                        trace.write('log_quote_not_found', quote=entry.quote, verdict=entry.verdict)
                    log.append(StoredLogCheck(**(entry.model_dump() | {
                        'paragraph': paragraph.id,
                        'scene': log_input['scene'] if entry.verdict == 'contradicted' else None,
                        'located': located,
                    })))
    hooks = KBHooks(root, run_dir, 'validator_contract', 1)
    options = session_options(
        root, run_dir, role, (root / 'prompts/validator_contract.md').read_text(),
        max_turns, hooks, tools=['Read', 'Grep'], output_format=json_schema_output(ContractReply))
    record_api_host(run_dir, options.env.get('ANTHROPIC_BASE_URL'))
    async with ClaudeSDKClient(options=options) as client:
        reply = await _call(client, json.dumps(dict(
            call='contract', paragraphs=paragraphs,
            style_specification=(root / 'prompts/style_spec.md').read_text(encoding='utf-8')),
            ensure_ascii=False),
            check=check_contract, stage='contract', role=role, hooks=hooks, trace=trace,
            cost=SessionCost(), options=options, parse=ContractReply.model_validate,
            agent='validator_contract')
        contract = []
        for finding in reply.findings:
            located = _quote_located(finding.quote, paragraph_text[finding.paragraph])
            if not located:
                trace.write('contract_quote_not_found', **finding.model_dump())
            contract.append(StoredContractFinding(**finding.model_dump(), located=located))
    checked = [CheckedClaim(**c.model_dump(), **(by_id[i].model_dump(exclude={'claim_id'}) |
                           (dict(verdict='unverified', claimed_verdict=by_id[i].verdict)
                            if i in failed else {})))
               if i in by_id else c for i, c in enumerate(claims)]
    report = Validation(rounds=[ValidationRound(
        round=1, claims=checked,
        not_in_kb=[c for c in checked if isinstance(c, CheckedClaim) and c.verdict == 'not_in_kb'],
        contradicted=sum(isinstance(c, CheckedClaim) and c.verdict == 'contradicted' for c in checked)
        + sum(entry.verdict == 'contradicted' for entry in log or []) + len(contract),
        log=log, contract=contract,
        unverified=[c for c in checked if isinstance(c, CheckedClaim) and c.verdict == 'unverified'],
    )])
    return report
