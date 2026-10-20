import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.world.io import load_state


@pytest.mark.e2e
def test_world_new(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, [
        "world", "new", "--characters", "agnea,throne", "--location", "cropdale",
        "--situation", "Agnea has brought Throné to a festival here.",
    ])
    assert result.exit_code == 0, result.output
    world = Path(result.output.strip())
    state = load_state(world)
    assert set(state.characters) == {"agnea", "throne"}
    info = json.loads((world / "world.json").read_text())
    run = root / "runs" / info["init_run_id"]
    retrieval = [json.loads(line) for line in (run / "retrieval.jsonl").read_text().splitlines()]
    assert retrieval and all(row["agent"] == "initializer" for row in retrieval)
    usage = [json.loads(line) for line in (run / "trace.jsonl").read_text().splitlines()
             if json.loads(line)["type"] == "stage_usage"]
    assert {row["stage"] for row in usage} == {"scene_context", "initializer_state"}
    assert all(row["usage"]["input_tokens"] > 0 and row["usage"]["output_tokens"] > 0 for row in usage)
