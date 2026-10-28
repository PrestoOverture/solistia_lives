"""Read append-only trace snapshots, allowing an incomplete final line."""

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel


class _Event(BaseModel):
    type: str
    ts: datetime
    stage: str | None = None
    error: str | None = None


def read_progress(run_dir: Path, created_at: datetime) -> dict:
    stage = "queued"
    validation_round = 0
    start = created_at
    end = datetime.now(timezone.utc)
    error = None
    try:
        lines = (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            event = _Event.model_validate_json(line)
        except ValueError:
            continue
        timestamp = event.ts.replace(tzinfo=event.ts.tzinfo or timezone.utc)
        if event.type == "run_started":
            start = timestamp
        if event.type in {"stage_started", "stage_finished", "stage_usage", "stage_failed"}:
            stage = event.stage or stage
        if event.type == "stage_started" and event.stage == "validate":
            validation_round += 1
        if event.type == "stage_failed":
            error = event.error
        if event.type == "run_finished":
            end = timestamp
    start = start.replace(tzinfo=start.tzinfo or timezone.utc)
    return dict(stage=stage, validation_round=validation_round,
                elapsed=int(max(0, (end - start).total_seconds())), error=error)
