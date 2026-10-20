import asyncio
import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from story_engine.simulation import TickSession, run_tick
from story_engine.world.io import load_state, read_events


@pytest.mark.e2e
def test_morning_tick(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    run = root / 'runs' / f'tick-{uuid4().hex}'
    run.mkdir(parents=True)
    world = run / 'world'
    shutil.copytree(root / 'tests/fixtures/worlds/agnea_throne', world)
    start = load_state(world)

    async def exercise():
        async with TickSession(world, run, root=root) as session:
            await run_tick(world, run, session=session)

    asyncio.run(exercise())
    state, events = load_state(world), read_events(world)
    assert state.clock.part == 'afternoon'
    for slug, character in state.characters.items():
        assert any(event.actor == slug for event in events)
        assert [event for event in events if slug in event.perceived_by][-1].place == character.where
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    notes = next(row['situation_notes'] for row in trace if row['type'] == 'situation_notes')
    assert {s.id for s in start.situations if s.status == 'open'} <= notes.keys()
