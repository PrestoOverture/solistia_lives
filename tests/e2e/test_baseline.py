import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from typer.testing import CliRunner

from story_engine.agents.sdk import session_environment
from story_engine.cli import app
from story_engine.config import load_configs


@pytest.mark.e2e
def test_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    relay = session_environment(root).get("ANTHROPIC_BASE_URL")
    assert relay, "Live baseline test requires a relay base URL"
    models, _ = load_configs()
    result = CliRunner().invoke(app, [
        "generate", "--mode", "baseline", "--characters", "osvald,temenos",
        "--location", "new_delsta", "--scenario", "catching up over drinks at a tavern",
    ])
    assert result.exit_code == 0, result.output
    run_dir = Path(result.output.strip())
    story = (run_dir / "story.md").read_text(encoding="utf-8")
    assert story.startswith("# ")
    assert 1800 <= len(story.split()) <= 3300
    meta = json.loads((run_dir / "meta.json").read_text())
    assert meta["status"] == "passed" and meta["error"] is None
    assert meta["api_host"] == urlsplit(relay).hostname
    assert meta["models"] == models.model_dump()
    trace = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text().splitlines()]
    assert [(e["type"], e.get("stage")) for e in trace] == [
        ("run_started", None),
        ("stage_started", "scene_context"), ("stage_usage", "scene_context"), ("stage_finished", "scene_context"),
        ("stage_started", "baseline_writer"), ("stage_usage", "baseline_writer"), ("stage_finished", "baseline_writer"),
        ("run_finished", None),
    ]
    for event in trace:
        if event["type"] == "stage_usage":
            assert event["usage"]["input_tokens"] > 0 and event["usage"]["output_tokens"] > 0
    assert trace[-2]["word_count"] == len(story.split())
    assert trace[-1]["status"] == "passed"
    retrieval = [json.loads(line) for line in (run_dir / "retrieval.jsonl").read_text().splitlines()]
    assert retrieval
    for entry in retrieval:
        assert entry["agent"] in ("initializer", "baseline")
        assert entry["tool"] in ("Read", "Grep", "Glob")
        assert not Path(entry["file"]).is_absolute()
        assert (root / "kb" / entry["file"]).resolve().is_relative_to(root / "kb")
