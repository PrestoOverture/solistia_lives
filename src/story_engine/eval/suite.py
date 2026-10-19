"""Run the author-written suite through the ordinary generate command."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
from typing import Literal

from pydantic import BaseModel, RootModel
import yaml

from story_engine.runs import RunInput, RunMeta


class SuiteCase(RunInput):
    id: str


class TestSuite(BaseModel):
    cases: list[SuiteCase]


class CaseResult(BaseModel):
    run_id: str | None = None
    status: Literal["dry_run", "running", "passed", "failed", "stopped"] = "failed"
    total_cost_usd: float | None = None


class SuiteManifest(RootModel[dict[str, CaseResult]]):
    """Case ID -> ordinary run ID, final status, and SDK cost in USD."""


def _sdk_cost(run_dir: Path, dry_run: bool) -> float | None:
    costs = []
    for line in (run_dir / "trace.jsonl").read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event["type"] == "stage_usage":
            cost = event.get("total_cost_usd")
            if cost is None:
                return None
            costs.append(cost)
    return sum(costs, 0.0) if costs or dry_run else None


def _generate_case(case: SuiteCase, models_file: Path, dry_run: bool) -> CaseResult:
    command = [
        sys.executable, "-c", "from story_engine.cli import app; app()", "generate",
        "--characters", ",".join(case.characters),
        "--location", case.location, "--scenario", case.scenario,
        "--mode", "baseline", "--models", str(models_file),
    ]
    if dry_run:
        command.append("--dry-run")
    result = CaseResult()
    try:
        process = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, check=False,
        )
        # generate prints the path alone on success, or "path: error" on failure.
        match = re.search(r"^runs/([\w-]+)(?=[:\r\n]|$)", process.stdout, re.MULTILINE)
        if match is None:
            return result
        result.run_id = match[1]
        run_dir = Path("runs") / result.run_id
        meta = RunMeta.model_validate_json((run_dir / "meta.json").read_bytes())
        result.total_cost_usd = _sdk_cost(run_dir, dry_run)
        result.status = meta.status if process.returncode == 0 else "failed"
    except (OSError, ValueError):
        # One failed invocation or unreadable artifact must not cancel other cases.
        result.status = "failed"
    return result


def run_suite(
    models_file: Path, dry_run: bool, suite_parallel: int,
) -> tuple[SuiteManifest, Path]:
    suite = TestSuite.model_validate(yaml.safe_load(Path("eval/test_suite.yaml").read_text()))
    with ThreadPoolExecutor(max_workers=suite_parallel) as executor:
        results = list(executor.map(
            lambda case: _generate_case(case, models_file, dry_run), suite.cases,
        ))
    manifest = SuiteManifest({case.id: result for case, result in zip(suite.cases, results)})
    directory = Path("runs/suites")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{secrets.token_hex(16)}.json"
    with path.open("x", encoding="utf-8") as file:
        file.write(manifest.model_dump_json(indent=2))
    return manifest, path
