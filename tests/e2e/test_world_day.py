import json
import shutil
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.world.io import read_events


@pytest.mark.e2e
def test_world_day(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    world = root / 'worlds' / f'day-{uuid4().hex}'
    shutil.copytree(root / 'tests/fixtures/worlds/agnea_throne', world)
    result = CliRunner().invoke(app, ['world', 'run', world.name, '--stop-after', 'day'])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert {(event.day, event.part) for event in read_events(world)} >= {
        (1, part) for part in ('morning', 'afternoon', 'evening', 'night')}
    for slug in ('agnea', 'throne'):
        assert (world / 'memory' / f'{slug}.md').read_text().strip()
    calls = defaultdict(list)
    for line in (run / 'trace.jsonl').read_text().splitlines():
        row = json.loads(line)
        if row['type'] == 'stage_usage':
            assert row.get('call_cost_usd') is not None
            calls[row['agent']].append(row)
    assert set(calls) == {'agnea', 'throne', 'world'}
    for rows in calls.values():
        assert len(rows) >= 2
        assert all(row['usage'].get('cache_read_input_tokens', 0) > 0 for row in rows[1:])
