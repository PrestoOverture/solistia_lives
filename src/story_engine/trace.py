"""Append-only run event trace."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable


class TraceWriter:
    def __init__(self, run_dir: Path, clock: Callable[[], datetime] | None = None,
                 on_usage: Callable[[float], None] | None = None) -> None:
        self.on_usage = on_usage
        self.path = run_dir / "trace.jsonl"
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._last_ts: datetime | None = None

    def write(self, event_type: str, **fields: object) -> None:
        now = self.clock().astimezone(timezone.utc)
        if self._last_ts is not None and now <= self._last_ts:
            now = self._last_ts + timedelta(microseconds=1)
        self._last_ts = now
        event = {**fields, "ts": now.isoformat(timespec="microseconds"), "type": event_type}
        with self.path.open("a", encoding="utf-8") as trace:
            trace.write(json.dumps(event, ensure_ascii=False) + "\n")
            trace.flush()
        if event_type == "stage_usage" and self.on_usage is not None:
            self.on_usage(float(fields.get("call_cost_usd") or 0.0))
