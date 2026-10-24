"""Shared validation and targeted-fix orchestration for completed drafts."""

import json
from pathlib import Path

from story_engine.agents import narrator
from story_engine.config import Models, Settings
from story_engine.trace import TraceWriter
from story_engine.agents.sdk import (
    KBHooks, SessionCost, SessionError, json_schema_output, session_options,
)
from story_engine.kb import TRAVELERS
from story_engine.runs import record_api_host
from story_engine.agents.validation import Validation, _call, validate_text


class ValidationStageError(SessionError):
    def __init__(self, stage, detail):
        self.stage = stage
        super().__init__(detail)


async def validate_and_fix(text: str, *, root: Path, run_dir: Path, models: Models,
                           settings: Settings, trace: TraceWriter, log_input: dict | None = None,
                           rounds: int | None = None) -> tuple[str, Validation]:
    """Persist the original draft and return final text and its validation history."""
    (run_dir / 'draft.md').write_bytes(text.encode('utf-8'))
    (run_dir / 'edits.json').write_text('[]', encoding='utf-8')
    stage = 'validate'
    try:
        trace.write('stage_started', stage=stage, agent='validator')
        report = await validate_text(
            text, root=root, run_dir=run_dir, role=models.validator,
            max_turns=settings.agent_max_turns, trace=trace, cost=SessionCost(), log_input=log_input,
        )
        (run_dir / 'validation.json').write_text(report.model_dump_json(indent=2), encoding='utf-8')
        trace.write('stage_finished', stage=stage)
        limit = settings.validation_rounds if rounds is None else rounds
        if not report.rounds[-1].contradicted or limit == 0:
            return text, report
        stage = 'fix'
        edits = []
        hooks = KBHooks(root, run_dir, 'narrator', 1)
        travelers = {e for claim in report.rounds[0].claims for e in claim.entities} & TRAVELERS
        sources = [root / 'prompts' / name for name in ('narrator_fix.md', 'style_spec.md', 'world_premise.md')]
        sources += [root / 'cards' / f'{slug}.md' for slug in sorted(travelers)]
        prompt = '\n\n'.join(path.read_text(encoding='utf-8') for path in sources)
        options = session_options(root, run_dir, models.narrator, prompt, settings.agent_max_turns, hooks, tools=['Read'],
                                  output_format=json_schema_output(narrator.FixReply))
        record_api_host(run_dir, options.env.get('ANTHROPIC_BASE_URL'))
        cost = SessionCost()
        async with narrator.ClaudeSDKClient(options=options) as client:
            for number in range(1, limit + 1):
                stage = 'fix'
                trace.write('stage_started', stage=stage, agent='narrator')
                items = narrator._fix_items(report.rounds[-1])
                hooks.turn = number
                reply = await _call(client, json.dumps(dict(text=text, fixes=items), ensure_ascii=False),
                                    parse=narrator.FixReply.model_validate, check=lambda r: narrator._check_edits(r, text, items),
                                    hooks=hooks, trace=trace, cost=cost, options=options,
                                    stage='fix', role=models.narrator, agent='narrator')
                text, changed = narrator._apply_edits(text, reply.edits)
                for edit in reply.edits:
                    edits.append(narrator.StoredFixEdit(round=number, fixes=[item for item in items if item['id'] in edit.fixes],
                                               old_string=edit.old_string, new_string=edit.new_string))
                (run_dir / 'edits.json').write_text(narrator.FixEdits(edits).model_dump_json(indent=2), encoding='utf-8')
                trace.write('stage_finished', stage='fix')
                stage = 'validate'
                trace.write('stage_started', stage=stage, agent='validator')
                checked = await validate_text(changed, root=root, run_dir=run_dir, role=models.validator,
                                              max_turns=settings.agent_max_turns, trace=trace, cost=SessionCost(), log_input=log_input)
                checked.rounds[0].round = number + 1
                report.rounds.extend(checked.rounds)
                (run_dir / 'validation.json').write_text(report.model_dump_json(indent=2), encoding='utf-8')
                trace.write('stage_finished', stage=stage)
                if not checked.rounds[0].contradicted:
                    break
        return text, report
    except Exception as error:
        detail = str(error) if isinstance(error, SessionError) else type(error).__name__
        trace.write('stage_failed', stage=stage, error=detail)
        raise ValidationStageError(stage, detail) from None
