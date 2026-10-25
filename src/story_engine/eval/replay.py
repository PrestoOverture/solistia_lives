"""Replay recorded World calls in fresh sessions, without persisting their results."""

import json
import shutil
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from story_engine.agents.sdk import SessionError
from story_engine.agents.world import (
    Encounter, OffscreenAgent, OffscreenEvent, WorldAgent,
)
from story_engine.config import load_configs
from story_engine.runs import RunMeta, create_run, finish_run
from story_engine.trace import TraceWriter
from story_engine.world.io import read_events
from story_engine.world.models import PartOfDay, Person, WorldState
from story_engine.world.ops import Op

Call = Literal["adjudicate", "offscreen"]


class CallInput(BaseModel):
    agent: str
    call: Call
    turn: int
    day: int
    part: PartOfDay
    state: dict
    max_event_id: int
    choices: dict = Field(default_factory=dict)
    validation_state: WorldState | None = None
    open_situations: set[str] = Field(default_factory=set)


class ReplayResult(BaseModel):
    call: Call
    turn: int
    day: int
    part: PartOfDay
    repeat: int
    cost_usd: float = 0.0
    ops: list[Op] = Field(default_factory=list)
    encounters: list[Encounter] = Field(default_factory=list)
    events: list[OffscreenEvent] = Field(default_factory=list)
    people: dict[str, Person] = Field(default_factory=dict)
    error: str | None = None


class ReplayReport(BaseModel):
    source_run_id: str
    results: list[ReplayResult] = Field(default_factory=list)


def _id(value: str, name: str) -> str:
    if not value or Path(value).name != value or value in (".", ".."):
        raise ValueError(f"{name} must be an ID")
    return value


async def replay(run_id: str, call: Call, turn: int | None = None, repeat: int = 1,
                 models_file: Path = Path("config/models.yaml")) -> tuple[Path, ReplayReport]:
    if call not in ("adjudicate", "offscreen"):
        raise ValueError("--call must be adjudicate or offscreen")
    if repeat < 1 or (turn is not None and turn < 1):
        raise ValueError("--repeat and --turn must be at least 1")
    source = Path("runs") / _id(run_id, "run_id")
    meta = RunMeta.model_validate_json((source / "meta.json").read_bytes())
    trace_path = source / "trace.jsonl"
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
    selected = [CallInput.model_validate(row) for row in rows
                if row.get("type") == "call_input" and row.get("call") == call
                and (turn is None or row.get("turn") == turn)]
    if not selected:
        raise ValueError(f"{run_id}: no call_input for {call}"
                         + (f" at turn {turn}" if turn is not None else "")
                         + "; replay requires a run recorded with call_input tracing")
    # Validate recorded inputs before creating a run or opening any model session.
    states = []
    for item in selected:
        state = (WorldState.model_validate(item.state) if call == "adjudicate"
                 else item.validation_state)
        if state is None:
            raise ValueError(f"{run_id}: offscreen call_input lacks validation_state")
        states.append(state)
    world_id = _id(meta.world_id or "", "source world_id")
    models, settings = load_configs(models_file)
    run_dir = create_run(**meta.input.model_dump(), mode="replay", stop_after=None,
                         models=models, status="running", world_id=world_id, day=meta.day,
                         models_file=str(models_file))
    trace = TraceWriter(run_dir)
    trace.write("run_started", mode="replay", source_run_id=run_id)
    (run_dir / "retrieval.jsonl").touch()
    report = ReplayReport(source_run_id=run_id)
    try:
        world_dir = run_dir / "world"
        shutil.copytree(Path("worlds") / world_id, world_dir)
        events = read_events(world_dir)
        for item, state in zip(selected, states):
            before = [event for event in events
                      if event.day == item.day and event.id <= item.max_event_id]
            for repetition in range(1, repeat + 1):
                result = ReplayResult(call=call, turn=item.turn, day=item.day, part=item.part,
                                      repeat=repetition)
                report.results.append(result)
                cls = WorldAgent if call == "adjudicate" else OffscreenAgent
                agent = cls(Path.cwd(), run_dir, world_dir, models.world,
                            settings.agent_max_turns, trace)
                try:
                    async with agent:
                        agent.turn = item.turn - 1
                        if call == "adjudicate":
                            event, encounters, _ = await agent.adjudicate(state, item.choices, before)
                            result.ops = event.ops if event is not None else []
                            result.encounters = encounters
                        else:
                            await agent.offscreen(state, item.open_situations,
                                                  max_event_id=item.max_event_id)
                            reply = agent.last_reply
                            result.events = reply.events
                except Exception as error:
                    result.error = str(error) if isinstance(error, SessionError) else f"{type(error).__name__}: {error}"
                    trace.write("stage_failed", call=call, turn=item.turn, repeat=repetition,
                                error=result.error)
                finally:
                    result.cost_usd = agent.cost.total
    except Exception as error:
        finish_run(run_dir, "failed", str(error))
        trace.write("run_finished", status="failed", error=str(error))
        raise
    finally:
        (run_dir / "replay.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    failed = [result.error for result in report.results if result.error]
    status = "failed" if failed else "passed"
    finish_run(run_dir, status, "; ".join(failed) if failed else None)
    trace.write("run_finished", status=status)
    return run_dir, report
