from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from threading import Event, Lock

import pytest
import yaml
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.config import load_configs
from story_engine.eval import suite as suite_module
from story_engine.kb import validate_input
from story_engine.runs import RunMeta, create_run, finish_run
from story_engine.trace import TraceWriter


REPO = Path(__file__).resolve().parents[2]


def test_sdk_cost_sums_per_call_deltas_for_one_session(tmp_path):
    trace = TraceWriter(tmp_path)
    for call_cost, total_cost in [(0.1, 0.1), (0.2, 0.3), (0.3, 0.6)]:
        trace.write("stage_usage", session_id="one-session",
                    call_cost_usd=call_cost, total_cost_usd=total_cost)

    assert suite_module._sdk_cost(tmp_path, False) == pytest.approx(0.6)


@pytest.mark.parametrize("usage,expected", [
    ({"total_cost_usd": 0.2}, 0.2),
    ({"call_cost_usd": 0.0, "total_cost_usd": 0.2}, 0.0),
    ({}, None),
    ({"call_cost_usd": None, "total_cost_usd": 0.2}, None),
])
def test_sdk_cost_fallback_and_missing_cost(tmp_path, usage, expected):
    TraceWriter(tmp_path).write("stage_usage", **usage)

    assert suite_module._sdk_cost(tmp_path, False) == expected


def test_author_suite_validates_against_real_kb(monkeypatch):
    repo = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(repo)
    cases = yaml.safe_load((repo / "eval/test_suite.yaml").read_text())["cases"]
    assert len(cases) == 10
    assert len({case["id"] for case in cases}) == 10
    groups = Counter(tuple(sorted(case["characters"])) for case in cases)
    assert len(groups) == 5
    assert set(groups.values()) == {2}
    prd = (repo / "docs/prd.md").read_text().split("### 6.4 Test Suite", 1)[1].split("### 6.5", 1)[0]
    situations = [line.split("|")[-2].strip() for line in prd.splitlines() if line.startswith("| ")][1:]
    group_keys = [("osvald", "temenos"), ("agnea", "throne"), ("hikari", "ochette"),
                  ("castti", "partitio"), ("agnea", "osvald", "temenos")]
    assert set(groups) == set(group_keys)
    for case in cases:
        group = group_keys.index(tuple(sorted(case["characters"])))
        assert case["situation"] == situations[group]
        assert "scenario" not in case
        characters, location = validate_input(
            ",".join(case["characters"]), case["location"],
        )
        assert characters == case["characters"], case["id"]
        assert location == case["location"], case["id"]


@pytest.fixture
def suite_workspace(tmp_path, monkeypatch):
    for name in ("config/models.yaml", "config/settings.yaml", "eval/test_suite.yaml"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((REPO / name).read_bytes())
    monkeypatch.chdir(tmp_path)
    return yaml.safe_load(Path("eval/test_suite.yaml").read_text())["cases"]


def fake_generate(monkeypatch, cases, parallel, *, failed=None, status=None, launch_error=None):
    """Fake only the child generate invocation; use real run and trace artifacts."""
    models, _ = load_configs()
    lock = Lock()
    ready = Event()
    state = {"active": 0, "peak": 0, "calls": [], "results": {}}

    def generate(command, **kwargs):
        assert command[:4] == [
            sys.executable, "-c", "from story_engine.cli import app; app()", "generate",
        ]
        assert kwargs == {
            "stdout": subprocess.PIPE, "stderr": subprocess.STDOUT,
            "text": True, "check": False,
        }
        assert "--stop-after" not in command
        assert "--stop" not in command
        options = {command[i]: command[i + 1] for i in range(4, 14, 2)}
        case = next(case for case in cases if (
            ",".join(case["characters"]) == options["--characters"]
            and case["location"] == options["--location"]
            and case["situation"] == options["--scenario"]
        ))
        with lock:
            state["calls"].append(command)
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            if state["active"] == parallel:
                ready.set()
        try:
            # Force the first wave to overlap without depending on timing or sleeps.
            assert ready.wait(timeout=5), "Configured concurrency was not reached"
            if case["id"] == launch_error:
                raise OSError("fake child launch failure")
            dry_run = "--dry-run" in command
            final_status = status or ("dry_run" if dry_run else "passed")
            if case["id"] == failed:
                final_status = "failed"
            run_dir = create_run(
                case["characters"], case["location"], case["situation"],
                options["--mode"], None, models,
                models_file=options["--models"],
            )
            trace = TraceWriter(run_dir)
            cost = 0.0
            if not dry_run:
                cost = (cases.index(case) + 1) / 100
                trace.write("stage_usage", stage="scene_context", total_cost_usd=cost)
                trace.write("stage_usage", stage="baseline_writer", total_cost_usd=cost * 2)
                cost *= 3
            trace.write("run_finished", status=final_status)
            if final_status != "dry_run":
                finish_run(run_dir, final_status)
            with lock:
                state["results"][case["id"]] = {
                    "run_id": run_dir.name, "status": final_status, "total_cost_usd": cost,
                }
            return subprocess.CompletedProcess(
                command, 1 if final_status == "failed" else 0,
                stdout=f"{run_dir}: baseline_writer failed: SessionError\n"
                if final_status == "failed" else f"{run_dir}\n",
            )
        finally:
            with lock:
                state["active"] -= 1

    monkeypatch.setattr(suite_module.subprocess, "run", generate)
    return state


def read_manifest(result, cases):
    lines = result.output.splitlines()
    assert len(lines) == len(cases) + 1, result.output
    assert [line.split(":", 1)[0] for line in lines[:-1]] == [case["id"] for case in cases]
    path = Path(lines[-1])
    assert path.parent == Path("runs/suites")
    manifest = json.loads(path.read_text())
    assert set(manifest) == {case["id"] for case in cases}
    return manifest


@pytest.mark.parametrize("parallel", [1, 3, 5])
@pytest.mark.parametrize("dry_run", [False, True])
def test_dispatches_all_cases_with_bounded_concurrency(suite_workspace, monkeypatch, parallel, dry_run):
    settings_path = Path("config/settings.yaml")
    settings = yaml.safe_load(settings_path.read_text())
    assert settings["suite_parallel"] == 5
    settings["suite_parallel"] = parallel
    settings_path.write_text(yaml.safe_dump(settings))
    alternate = Path("alternate models.yaml")
    alternate.write_bytes(Path("config/models.yaml").read_bytes())
    cases = suite_workspace
    state = fake_generate(monkeypatch, cases, parallel)

    args = ["eval", "run-suite", "--mode", "baseline", "--models", str(alternate)]
    if dry_run:
        args.append("--dry-run")
    result = CliRunner().invoke(app, args)

    assert result.exit_code == 0, result.output
    assert len(state["calls"]) == 10
    assert state["active"] == 0
    assert state["peak"] == parallel
    manifest = read_manifest(result, cases)
    assert len({entry["run_id"] for entry in manifest.values()}) == 10
    for case in cases:
        entry = manifest[case["id"]]
        expected = state["results"][case["id"]]
        assert entry["run_id"] == expected["run_id"]
        assert entry["status"] == ("dry_run" if dry_run else "passed")
        assert entry["total_cost_usd"] == pytest.approx(expected["total_cost_usd"])
        meta = RunMeta.model_validate_json((Path("runs") / entry["run_id"] / "meta.json").read_bytes())
        assert meta.input.model_dump() == {"characters": case["characters"], "location": case["location"], "scenario": case["situation"]}
        assert meta.models_file == str(alternate)
        assert meta.mode == "baseline"
        assert meta.stop_after is None


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("failure", ["failed", "launch_error"])
def test_failure_is_recorded_and_other_cases_finish(suite_workspace, monkeypatch, dry_run, failure):
    cases = suite_workspace
    failed_id = cases[2]["id"]
    state = fake_generate(monkeypatch, cases, 5, **{failure: failed_id})
    args = ["eval", "run-suite", "--mode", "baseline"]
    if dry_run:
        args.append("--dry-run")
    result = CliRunner().invoke(app, args)

    assert result.exit_code == 1, result.output
    assert len(state["calls"]) == 10
    assert state["active"] == 0
    manifest = read_manifest(result, cases)
    for case in cases:
        entry = manifest[case["id"]]
        if case["id"] == failed_id and failure == "launch_error":
            assert entry == {"run_id": None, "world_id": None, "init_run_id": None, "status": "failed", "total_cost_usd": None}
        else:
            assert entry["run_id"] == state["results"][case["id"]]["run_id"]
            assert entry["total_cost_usd"] == pytest.approx(state["results"][case["id"]]["total_cost_usd"])
            assert entry["status"] == ("failed" if case["id"] == failed_id else ("dry_run" if dry_run else "passed"))


@pytest.mark.parametrize("dry_run,status", [(False, "stopped"), (False, "dry_run"), (True, "passed")])
def test_unexpected_final_status_exits_one(suite_workspace, monkeypatch, dry_run, status):
    fake_generate(monkeypatch, suite_workspace, 5, status=status)
    args = ["eval", "run-suite", "--mode", "baseline"]
    if dry_run:
        args.append("--dry-run")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1, result.output
    manifest = read_manifest(result, suite_workspace)
    assert {entry["status"] for entry in manifest.values()} == {status}


@pytest.mark.parametrize("failed", [False, True])
def test_simulation_dispatch_and_manifest(suite_workspace, monkeypatch, failed):
    cases = suite_workspace
    models, _ = load_configs()
    calls = []
    Path("alternate.yaml").write_bytes(Path("config/models.yaml").read_bytes())
    expected = {}
    lock = Lock()

    def child(command, **kwargs):
        assert command[:4] == [sys.executable, "-c", "from story_engine.cli import app; app()", "world"]
        assert kwargs == dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        assert "--stop-after" not in command
        with lock:
            calls.append(command)
        if command[4] == "new":
            options = dict(zip(command[5::2], command[6::2]))
            case = next(c for c in cases if c["location"] == options["--location"]
                        and ",".join(c["characters"]) == options["--characters"])
            assert options["--situation"] == case["situation"]
            assert options["--models"] == "alternate.yaml"
            run = create_run(case["characters"], case["location"], case["situation"], "initializer", None, models)
            TraceWriter(run).write("stage_usage", total_cost_usd=0.25)
            is_failed = failed and case == cases[0]
            finish_run(run, "failed" if is_failed else "passed")
            world_id = "world-" + case["id"]
            expected[case["id"]] = dict(world_id=None if is_failed else world_id,
                                             init_run_id=run.name, run_id=None,
                                             status="failed" if is_failed else "passed",
                                             total_cost_usd=0.25 if is_failed else 1.0)
            if is_failed:
                return subprocess.CompletedProcess(command, 1, stdout=f"{run}: initializer failed\n")
            world = Path("worlds") / world_id
            world.mkdir(parents=True)
            (world / "world.json").write_text(json.dumps({"init_run_id": run.name}))
            return subprocess.CompletedProcess(command, 0, stdout=f"{world}\n")
        assert command[4] == "run" and len(command) == 8
        assert command[6:] == ["--models", "alternate.yaml"]
        case = next(c for c in cases if "world-" + c["id"] == command[5])
        assert not (failed and case == cases[0])
        assert expected[case["id"]]["init_run_id"]
        run = create_run(case["characters"], case["location"], case["situation"], "simulation", None, models)
        TraceWriter(run).write("stage_usage", total_cost_usd=0.75)
        finish_run(run, "passed")
        expected[case["id"]]["run_id"] = run.name
        return subprocess.CompletedProcess(command, 0, stdout=f"{run}\n")

    monkeypatch.setattr(suite_module.subprocess, "run", child)
    result = CliRunner().invoke(app, ["eval", "run-suite", "--mode", "simulation", "--models", "alternate.yaml"])
    assert result.exit_code == (1 if failed else 0), result.output
    assert len(calls) == (19 if failed else 20)
    assert read_manifest(result, cases) == expected
