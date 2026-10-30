"""Model-only recovery of missing minor-character sex, preserving historical data."""

import json
from pathlib import Path
from typing import Literal

import frontmatter
from claude_agent_sdk import ClaudeSDKClient, ResultMessage
from pydantic import BaseModel, ConfigDict

from story_engine.agents.sdk import (
    KBHooks, SessionError, json_schema_output, run_call, session_error,
    session_options, structured_reply,
)
from story_engine.config import load_configs
from story_engine.kb import normalize_slug
from story_engine.runs import create_run, finish_run, record_api_host
from story_engine.trace import TraceWriter
from .io import _atomic_write, _read_json, _unique_object, load_state, require_genesis, validate_state
from .models import Event, WorldInfo, WorldState
from .ops import reduce_ops


class SexReply(BaseModel):
    model_config = ConfigDict(extra='forbid')
    people: dict[str, Literal['m', 'f']]


async def backfill_sex(root: Path, world_dir: Path, models_file: Path) -> tuple[int, int]:
    """Ask once for all missing people, validate the full fold, then replace artifacts."""
    require_genesis(world_dir)
    state = load_state(world_dir)
    missing = {name: person for name, person in state.people.items() if person.sex is None}
    skipped = len(state.people) - len(missing)
    if not missing:
        return 0, skipped
    models, settings = load_configs(models_file)
    info = WorldInfo.model_validate(_read_json(world_dir / 'world.json'))
    cards = {}
    for path in sorted((root / 'kb').rglob('*.md')):
        metadata = frontmatter.load(path).metadata
        for alias in [path.stem, metadata.get('name', ''), *metadata.get('aliases', [])]:
            cards.setdefault(normalize_slug(alias), []).append(path)
    people = []
    for name, person in missing.items():
        paths = dict.fromkeys(cards.get(normalize_slug(name), []))
        people.append(dict(name=name, wants=person.wants,
                           kb_cards=[path.read_text(encoding='utf-8') for path in paths]))
    run_dir = create_run(info.characters, info.location, info.situation, 'backfill_sex', None,
                         models, status='running', models_file=str(models_file),
                         world_id=world_dir.name, runs_dir=root / 'runs')
    trace = TraceWriter(run_dir)
    trace.write('run_started', run_id=run_dir.name, mode='backfill_sex')
    try:
        hooks = KBHooks(root, run_dir, agent='world', turn=0)
        output = json_schema_output(SexReply)
        output['schema']['properties']['people'] = {
            'type': 'object', 'properties': {name: {'type': 'string', 'enum': ['m', 'f']} for name in missing},
            'required': list(missing), 'additionalProperties': False,
        }
        options = session_options(root, run_dir, models.world,
                                  'Assign each supplied person a sex for appearance and voice, using their KB card when supplied.',
                                  settings.agent_max_turns, hooks, tools=[], output_format=output)
        record_api_host(run_dir, options.env.get('ANTHROPIC_BASE_URL'))
        async with ClaudeSDKClient(options=options) as client:
            async def receive():
                await client.query(json.dumps({'people': people}, ensure_ascii=False))
                async for message in client.receive_response():
                    if isinstance(message, ResultMessage):
                        trace.write('stage_usage', stage='backfill_sex', agent='world',
                                    usage=message.usage or {}, num_turns=message.num_turns,
                                    total_cost_usd=message.total_cost_usd)
                        if message.is_error or message.subtype != 'success':
                            raise session_error(message.result or message.subtype, options.env)
                        return SexReply.model_validate(structured_reply(message.result, message.structured_output))
                raise SessionError('Sex backfill returned no result')
            reply = await run_call(receive(), role=models.world, trace=trace,
                                   stage='backfill_sex', agent='world')
        if set(reply.people) != set(missing):
            raise ValueError('Sex backfill must return exactly the requested names')
        genesis_path = world_dir / 'genesis.json'
        genesis = _read_json(genesis_path)
        for name, person in genesis.get('people', {}).items():
            if name in missing:
                person['sex'] = reply.people[name]
        events_path = world_dir / 'events.jsonl'
        lines = events_path.read_text(encoding='utf-8').splitlines(keepends=True)
        folded = WorldState.model_validate(genesis)
        for index, line in enumerate(lines):
            data = json.loads(line, object_pairs_hook=_unique_object)
            changed = False
            for op in data.get('ops', []):
                if op['op'] == 'introduce' and op['name'] in missing:
                    op['sex'] = reply.people[op['name']]
                    changed = True
            event = Event.model_validate(data)
            folded = reduce_ops(folded, event.ops, event_id=event.id, scene=event.scene)
            if changed:
                lines[index] = json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n'
        folded = validate_state(world_dir, folded)
        if any(person.sex is None for person in folded.people.values()):
            raise ValueError('Sex backfill left people without sex')
        _atomic_write(genesis_path, json.dumps(genesis, ensure_ascii=False, indent=2))
        _atomic_write(events_path, ''.join(lines))
        _atomic_write(world_dir / 'state.json', folded.model_dump_json(indent=2))
    except Exception:
        trace.write('run_finished', status='failed')
        finish_run(run_dir, 'failed')
        raise
    trace.write('run_finished', status='passed')
    finish_run(run_dir, 'passed')
    return len(missing), skipped
