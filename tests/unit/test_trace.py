import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.trace import TraceWriter


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = Path(__file__).resolve().parents[2] / "config"
    target = tmp_path / "config"
    target.mkdir()
    for name in ("models.yaml", "settings.yaml"):
        (target / name).write_bytes((source / name).read_bytes())
    monkeypatch.chdir(tmp_path)
    return target


def test_dry_run_trace(config_dir: Path) -> None:
    result = CliRunner().invoke(app, [
        "generate", "--dry-run", "--characters", "osvald,temenos",
        "--location", "new_delsta", "--scenario", "x", "--mode", "baseline",
    ])
    assert result.exit_code == 0
    run_dir = Path(result.output.strip())
    events = [json.loads(line) for line in (run_dir / "trace.jsonl").read_text().splitlines()]
    assert len(events) == 2
    assert [event["type"] for event in events] == ["run_started", "run_finished"]
    assert events[0]["run_id"] == run_dir.name
    assert events[0]["mode"] == "baseline"
    assert events[1]["status"] == "dry_run"
    timestamps = [datetime.fromisoformat(event["ts"]) for event in events]
    assert timestamps[0] < timestamps[1]
    assert all(ts.utcoffset().total_seconds() == 0 for ts in timestamps)
    assert all(len(event["ts"].split(".")[-1].split("+")[0]) == 6 for event in events)


def test_frozen_clock_still_increases(tmp_path: Path) -> None:
    frozen = datetime(2026, 1, 1, tzinfo=timezone.utc)
    writer = TraceWriter(tmp_path, clock=lambda: frozen)
    for _ in range(3):
        writer.write("example")
    timestamps = [datetime.fromisoformat(json.loads(line)["ts"])
                  for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
    assert timestamps[0] < timestamps[1] < timestamps[2]


def test_second_writer_appends_without_changing_existing_bytes(tmp_path: Path) -> None:
    first = TraceWriter(tmp_path)
    first.write("first", message="乾杯")
    path = tmp_path / "trace.jsonl"
    original = path.read_bytes()
    second = TraceWriter(tmp_path)
    second.write("second")
    updated = path.read_bytes()
    assert updated.startswith(original)
    assert len(updated.splitlines()) == 2
    assert json.loads(updated.splitlines()[1])["type"] == "second"
