import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from story_engine.agents.character import Action, CharacterAgent
from story_engine.config import load_configs
from story_engine.trace import TraceWriter


@pytest.mark.e2e
def test_character_action(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    models, settings = load_configs()
    run = root / "runs" / f"character-action-{uuid4().hex}"
    run.mkdir(parents=True)
    world = root / "tests/fixtures/worlds/agnea_throne"

    async def exercise():
        async with CharacterAgent(root, run, world, "throne", models.character,
                                  settings.turn_cap, TraceWriter(run)) as agent:
            return await agent.act([])

    action = asyncio.run(exercise())
    assert isinstance(action, Action)
    assert action.intent.strip() and action.move in {"act", "wait", "leave"}
    trace = [json.loads(line) for line in (run / "trace.jsonl").read_text().splitlines()]
    assert any(row["type"] == "stage_usage" and row["agent"] == "throne" for row in trace)
