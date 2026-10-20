import asyncio
import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from story_engine.simulation import TickSession, run_tick


@pytest.mark.e2e
def test_morning_scene(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    run = root / 'runs' / f'scene-{uuid4().hex}'
    run.mkdir(parents=True)
    world = run / 'world'
    shutil.copytree(root / 'tests/fixtures/worlds/agnea_throne', world)

    async def exercise():
        async with TickSession(world, run, root=root) as session:
            await run_tick(world, run, session=session)

    asyncio.run(exercise())
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert any(row['type'] == 'scene_round' and row['place'] == 'festival_grounds'
               for row in trace)
    endings = [row for row in trace if row['type'] == 'scene_ended'
               and row['place'] == 'festival_grounds']
    assert endings and all(row['reason'] != 'scene_cap_reached' for row in endings)
