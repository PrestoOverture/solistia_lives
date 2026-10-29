"""Recover committed scene move fields by joining recorded simulation traces."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from .io import _atomic_write, _unique_object
from .models import Event


class _MoveLines(BaseModel):
    move: Literal['act', 'wait', 'leave']
    action: str
    say: str


def backfill_lines(world_dir: Path, runs_dir: Path) -> int:
    """Validate the entire join before atomically replacing only action/say fields."""
    moves = {}
    for meta_path in sorted(runs_dir.glob('*/meta.json')):
        meta = json.loads(meta_path.read_bytes(), object_pairs_hook=_unique_object)
        if meta.get('mode') != 'simulation' or meta.get('world_id') != world_dir.name:
            continue
        trace_path = meta_path.parent / 'trace.jsonl'
        if not trace_path.exists():
            continue
        for line in trace_path.read_text(encoding='utf-8').splitlines():
            row = json.loads(line, object_pairs_hook=_unique_object)
            if row.get('type') != 'scene_round':
                continue
            if meta.get('day') is None:
                raise ValueError(f'Missing simulation day: {meta_path}')
            for actor, data in row['moves'].items():
                key = (meta['day'], row['scene'], row['round'], actor)
                move = _MoveLines.model_validate(data)
                if key in moves and moves[key] != move:
                    raise ValueError(f'Conflicting traces for move {key}: {trace_path}')
                moves[key] = move

    path = world_dir / 'events.jsonl'
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    updated = 0
    for index, line in enumerate(lines):
        data = json.loads(line, object_pairs_hook=_unique_object)
        event = Event.model_validate(data)
        if event.scene is None or event.type not in {'speech', 'action'}:
            continue
        key = (event.day, event.scene, event.round, event.actor)
        move = moves.get(key)
        if move is None:
            if event.type == 'speech':
                raise ValueError(f'No matching move for speech event {event.id}: {key}')
            continue
        fields = dict(action=move.action, say=move.say if move.move != 'wait' and move.say else None)
        if all(name in data and data[name] == value for name, value in fields.items()):
            continue
        data.update(fields)
        lines[index] = json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n'
        updated += 1
    if updated:
        _atomic_write(path, ''.join(lines))
    return updated
