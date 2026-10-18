import json
import os
import shlex
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from typer.testing import CliRunner

from story_engine.cli import app


@pytest.mark.e2e
def test_scene_context(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    dotenv_host = None
    for line in (root / ".env").read_text(encoding="utf-8").splitlines():
        key, separator, value = line.strip().removeprefix("export ").lstrip().partition("=")
        if separator and key.strip() == "ANTHROPIC_BASE_URL":
            parts = shlex.split(value, comments=True)
            dotenv_host = urlsplit(parts[0]).hostname if parts else None
    assert dotenv_host is not None, "Live scene context test requires a .env base URL"
    inherited_env = dict(os.environ)
    result = CliRunner().invoke(app, [
        "generate", "--mode", "baseline", "--stop-after", "scene_context",
        "--characters", "osvald,temenos", "--location", "new_delsta",
        "--scenario", "catching up over drinks at a tavern",
    ])
    assert result.exit_code == 0, result.output
    environment_unchanged = dict(os.environ) == inherited_env
    assert environment_unchanged, "The CLI must preserve the inherited environment"
    run_dir = Path(result.output.strip())
    context = (run_dir / "scene_context.md").read_text(encoding="utf-8")
    assert context.splitlines()[0].startswith("## ")
    assert all(name in context for name in ("New Delsta", "Osvald", "Temenos"))
    entries = [json.loads(line) for line in (run_dir / "retrieval.jsonl").read_text().splitlines()]
    reads = [entry for entry in entries if entry["tool"] == "Read"]
    assert len(reads) >= 3
    assert any(entry["file"] == "locations/brightlands/towns/new_delsta.md" for entry in reads)
    for entry in entries:
        assert not Path(entry["file"]).is_absolute()
        assert (root / "kb" / entry["file"]).resolve().is_relative_to(root / "kb")
        assert entry["turn"] == 0 and entry["agent"] == "director"
    meta = json.loads((run_dir / "meta.json").read_text())
    assert meta["status"] == "stopped"
    assert meta["api_host"] == dotenv_host
    trace = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text().splitlines()]
    usage = next(event["usage"] for event in trace if event["type"] == "stage_usage")
    assert usage["input_tokens"] > 0 and usage["output_tokens"] > 0
