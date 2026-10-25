"""Read-only world-day evaluation: data metrics and one semantic judge session."""

import json
from pathlib import Path
from typing import Literal, get_args

from claude_agent_sdk import ClaudeSDKClient, ResultMessage

from story_engine.agents.sdk import (
    run_call, KBHooks, SessionCost, SessionError, json_schema_output, session_error,
    session_options, structured_reply,
)
from story_engine.config import StrictModel, load_configs
from story_engine.runs import create_run, finish_run, record_api_host
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state, read_events, read_scenes
from story_engine.world.models import WorldInfo

Metric = Literal['interactions_staged', 'state_follows_log', 'canon_and_scope', 'continuity']


class Finding(StrictModel):
    metric: Metric
    event_ids: list[int]
    state_refs: list[str]
    explanation: str


class Findings(StrictModel):
    findings: list[Finding]


class Counts(StrictModel):
    scenes: int
    scene_rounds: int
    part_of_day_outcomes: int


class WorldReport(Findings):
    world_id: str
    day: int
    completion: bool
    overdue_situations: list[str] | None
    counts: Counts
    cost_usd: float = 0.0
    judge_status: Literal['skipped', 'passed', 'failed'] = 'skipped'
    error: str | None = None


async def judge(root, run_dir, payload, role, max_turns, trace, cost):
    hooks = KBHooks(root, run_dir, 'world_judge', 1)
    options = session_options(
        root, run_dir, role, (root / 'prompts/world_judge.md').read_text(), max_turns,
        hooks, tools=['Read', 'Grep'], output_format=json_schema_output(Findings),
    )
    record_api_host(run_dir, options.env.get('ANTHROPIC_BASE_URL'))
    allowed_ids = {row['id'] for key in ('events', 'previous_events') for row in payload[key]}
    outcome_ids = {row['id'] for row in payload['outcomes']}
    request = json.dumps(payload, ensure_ascii=False)
    async with ClaudeSDKClient(options=options) as client:
        for attempt in range(role.retries + 1):
            async def receive_call():
                await client.query(request)
                result = structured = None
                async for message in client.receive_response():
                    hooks.observe(message)
                    if isinstance(message, ResultMessage):
                        trace.write('stage_usage', stage='world_eval', agent='world_judge',
                                    attempt=attempt + 1, usage=message.usage or {},
                                    num_turns=message.num_turns, total_cost_usd=message.total_cost_usd,
                                    call_cost_usd=cost.delta(message.total_cost_usd))
                        if message.is_error or message.subtype != 'success':
                            raise session_error(f'World judge {message.subtype}: '
                                                + ('; '.join(message.errors or []) or message.result or 'SDK error'), options.env)
                        result, structured = message.result, message.structured_output
                return result, structured
            result, structured = await run_call(receive_call(), role=role, trace=trace, stage="world_eval", agent="world_judge")
            try:
                reply = Findings.model_validate(structured_reply(result, structured))
                unknown = {i for f in reply.findings for i in f.event_ids} - allowed_ids
                if unknown:
                    raise ValueError(f'unknown event ids: {sorted(unknown)}')
                for finding in reply.findings:
                    if not finding.event_ids and not finding.state_refs:
                        raise ValueError('every finding must cite at least one event id or state_ref')
                    if finding.metric == 'interactions_staged':
                        invalid = set(finding.event_ids) - outcome_ids
                        if invalid:
                            raise ValueError('interactions_staged may cite only outcomes of the day: '
                                             f'{sorted(invalid)}')
                    if finding.metric == 'continuity' and payload['day'] == 1:
                        raise ValueError('continuity findings are not allowed on day 1')
                return reply.findings
            except ValueError as error:
                if attempt == role.retries:
                    raise SessionError(f'World judge validation failed after {"one retry" if role.retries == 1 else str(role.retries) + " retries"}: {error}') from None
                request = f'Reply validation failed: {error}\nReturn corrected structured output.'
    raise AssertionError('unreachable')


async def evaluate_world(world_id: str, day: int | None = None,
                         models_file: Path = Path("config/models.yaml")):
    if Path(world_id).name != world_id or world_id in ('', '.', '..'):
        raise ValueError('world_id must be a world ID')
    models, settings = load_configs(models_file)
    world_dir = Path('worlds') / world_id
    current = load_state(world_dir)
    first_part = settings.parts_of_day[0]
    latest_day = current.clock.day - (current.clock.part == first_part)
    if day is None:
        day = latest_day
    if day < 1:
        raise ValueError('day must be at least 1')
    if day < latest_day:
        raise ValueError(f'{world_id}: only the latest simulated day can be checked')
    if day > latest_day:
        raise ValueError(f'{world_id}: day {day} has not been simulated')
    end = current if (current.clock.day, current.clock.part) == (day + 1, first_part) else None
    events = [event for event in read_events(world_dir) if not event.op_only]
    today = [e for e in events if e.day == day]
    previous = [e for e in events if day >= 2 and e.day == day - 1]
    scenes = [s for s in read_scenes(world_dir) if s.day == day]
    info = WorldInfo.model_validate_json((world_dir / 'world.json').read_bytes())
    run_dir = create_run(info.characters, info.location, info.situation, 'world_eval', None,
                         models, status='running', world_id=world_id, day=day, models_file=str(models_file))
    trace = TraceWriter(run_dir)
    trace.write('run_started', mode='world_eval', world_id=world_id, day=day)
    (run_dir / 'retrieval.jsonl').touch()
    report = WorldReport(
        world_id=world_id, day=day, completion=end is not None, findings=[],
        overdue_situations=None if end is None else [
            s.id for s in end.situations if s.status == 'open' and s.due.day <= day],
        counts=Counts(scenes=len(scenes), scene_rounds=sum(s.rounds for s in scenes),
                      part_of_day_outcomes=sum(e.scene is None and e.of is not None for e in today)),
    )
    cost = SessionCost()
    status = 'passed'
    try:
        if end is not None:
            report.findings = await judge(Path.cwd(), run_dir, {
                'day': day, 'end_state': end.model_dump(),
                'events': [e.model_dump() for e in today],
                'outcomes': [e.model_dump() for e in today if e.scene is None and e.of is not None],
                'scenes': [s.model_dump() for s in scenes],
                'previous_events': [e.model_dump() for e in previous],
            }, models.world_judge, settings.agent_max_turns, trace, cost)
            report.judge_status = 'passed'
    except Exception as error:
        status = report.judge_status = 'failed'
        report.error = str(error) if isinstance(error, SessionError) else f'{type(error).__name__}: {error}'
        trace.write('stage_failed', stage='world_eval', error=report.error)
    report.cost_usd = cost.total
    (run_dir / 'world_report.json').write_text(report.model_dump_json(indent=2), encoding='utf-8')
    finish_run(run_dir, status, report.error)
    trace.write('run_finished', status=status)
    return run_dir, report


def summary(run_dir: Path, report: WorldReport) -> str:
    counts = ' '.join(f'{metric}={sum(f.metric == metric for f in report.findings)}'
                      for metric in get_args(Metric))
    return (f'{report.world_id} day={report.day} run={run_dir.name} '
            f'completion={str(report.completion).lower()} {counts} cost=${report.cost_usd:.6f}')
