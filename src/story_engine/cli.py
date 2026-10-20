import asyncio
from pathlib import Path

import typer
from typing import Literal

from story_engine.config import ConfigError, load_configs, valid_stop
from story_engine.eval.pack import pack_runs
from story_engine.eval.suite import run_suite
from story_engine.kb import validate_input
from story_engine.agents.baseline import baseline_writer
from story_engine.agents.initializer import scene_context, starting_state
from story_engine.world.io import create_world
from story_engine.agents.sdk import SessionError
from story_engine.runs import RunInput, create_run, finish_run, read_scene_context
from story_engine.trace import TraceWriter

app = typer.Typer(help="Generate Octopath Traveler II stories.")
kb_app = typer.Typer(help="Build and check the knowledge base.")
eval_app = typer.Typer(help="Evaluate generated stories.")


@app.command()
def generate(
    characters: str = typer.Option(..., help="Comma-separated character slugs"),
    location: str = typer.Option(...),
    scenario: str = typer.Option(...),
    mode: Literal["pipeline", "baseline"] = typer.Option(...),
    stop: str | None = typer.Option(None),
    stop_after: Literal["scene_context", "beat_plan", "transcript"] | None = typer.Option(None),
    dry_run: bool = typer.Option(False),
    scene_context_from: str | None = typer.Option(None, help="Reuse scene context from this run ID"),
    models_file: Path = typer.Option(Path("config/models.yaml"), "--models", help="Models YAML file"),
) -> None:
    """Generate a story."""
    try:
        models, settings = load_configs(models_file)
    except ConfigError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)
    try:
        resolved_stop = valid_stop(stop if stop is not None else settings.default_stop)
    except ValueError as error:
        typer.echo(f"--stop: {error}", err=True)
        raise typer.Exit(code=1)
    try:
        character_slugs, location_slug = validate_input(characters, location)
    except ValueError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1)
    if mode == "baseline" and stop_after in ("beat_plan", "transcript"):
        typer.echo(f"--stop-after {stop_after} is not available in baseline mode", err=True)
        raise typer.Exit(code=1)
    reused_context = None
    if scene_context_from is not None:
        if stop_after == "scene_context":
            typer.echo("--scene-context-from cannot be combined with --stop-after scene_context", err=True)
            raise typer.Exit(code=1)
        try:
            reused_context = read_scene_context(
                scene_context_from,
                RunInput(characters=character_slugs, location=location_slug, scenario=scenario),
            )
        except ValueError as error:
            typer.echo(str(error), err=True)
            raise typer.Exit(code=1) from None
    if dry_run:
        run_dir = create_run(
            character_slugs,
            location_slug,
            scenario,
            mode,
            resolved_stop,
            stop_after,
            models,
            scene_context_from=scene_context_from, models_file=str(models_file),
        )
        trace = TraceWriter(run_dir)
        trace.write("run_started", run_id=run_dir.name, mode=mode)
        trace.write("run_finished", status="dry_run")
        typer.echo(run_dir)
        return
    if stop_after == "scene_context" or (mode == "baseline" and stop_after is None):
        run_dir = create_run(
            character_slugs, location_slug, scenario, mode, resolved_stop, stop_after,
            models, status="running",
            scene_context_from=scene_context_from, models_file=str(models_file),
        )
        trace = TraceWriter(run_dir)
        trace.write("run_started", run_id=run_dir.name, mode=mode)
        stage = "scene_context"
        try:
            if reused_context is not None:
                (run_dir / "scene_context.md").write_bytes(reused_context)
                trace.write("stage_reused", stage=stage, scene_context_from=scene_context_from)
            else:
                trace.write("stage_started", stage=stage, agent="initializer")
                asyncio.run(scene_context(
                    Path.cwd(), run_dir, character_slugs, location_slug, scenario,
                    models.initializer, settings.scene_context_max_turns, trace,
                ))
                trace.write("stage_finished", stage=stage)
            if stop_after == "scene_context":
                status = "stopped"
            else:
                stage = "baseline_writer"
                trace.write("stage_started", stage=stage, agent="baseline")
                asyncio.run(baseline_writer(
                    Path.cwd(), run_dir, character_slugs, location_slug, scenario,
                    models.baseline, settings.words, settings.writer_max_turns, trace,
                ))
                draft = (run_dir / "draft.md").read_bytes()
                (run_dir / "story.md").write_bytes(draft)
                trace.write("stage_finished", stage=stage, word_count=len(draft.decode("utf-8").split()))
                status = "passed"
            finish_run(run_dir, status)
        except Exception as error:
            # Exception messages can include credentials from the relay or SDK.
            detail = str(error) if isinstance(error, SessionError) else type(error).__name__
            summary = f"{stage} failed: {detail}"
            (run_dir / "story.md").unlink(missing_ok=True)
            finish_run(run_dir, "failed", summary)
            trace.write("stage_failed", stage=stage, error=summary)
            trace.write("run_finished", status="failed")
            typer.echo(f"{run_dir}: {summary}", err=True)
            raise typer.Exit(code=1) from None
        trace.write("run_finished", status=status)
        typer.echo(run_dir)
        return
    typer.echo("not implemented")
    raise typer.Exit(code=1)


@kb_app.callback()
def kb() -> None:
    """Build and check the knowledge base."""


@eval_app.callback()
def evaluate() -> None:
    """Evaluate generated stories."""


@eval_app.command("run-suite")
def run_suite_command(
    mode: Literal["baseline", "pipeline"] = typer.Option(...),
    models_file: Path = typer.Option(Path("config/models.yaml"), "--models", help="Models YAML file"),
    dry_run: bool = typer.Option(False),
) -> None:
    """Run every case in eval/test_suite.yaml."""
    if mode == "pipeline":
        typer.echo("pipeline mode is not implemented", err=True)
        raise typer.Exit(code=1)
    try:
        _, settings = load_configs(models_file)
        manifest, path = run_suite(models_file, dry_run, settings.suite_parallel)
    except (ConfigError, OSError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None
    for case_id, result in manifest.root.items():
        cost = "unknown" if result.total_cost_usd is None else f"${result.total_cost_usd:.6f}"
        typer.echo(f"{case_id}: {result.run_id or '-'} {result.status} {cost}")
    typer.echo(path)
    expected = "dry_run" if dry_run else "passed"
    if any(result.status != expected for result in manifest.root.values()):
        raise typer.Exit(code=1)


@eval_app.command()
def pack(
    run_id: str = typer.Argument(...),
    second_run_id: str | None = typer.Argument(None),
) -> None:
    """Pack one or two finished runs for blind judging."""
    try:
        _, settings = load_configs()
        run_ids = [run_id] if second_run_id is None else [run_id, second_run_id]
        packets, key_path = pack_runs(run_ids, settings.blind_root)
    except (ConfigError, OSError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None
    for path in [*packets, key_path]:
        typer.echo(path)


app.add_typer(kb_app, name="kb")
app.add_typer(eval_app, name="eval")


world_app = typer.Typer(help="Create persistent worlds.")
app.add_typer(world_app, name="world")


@world_app.command("new")
def world_new(
    characters: str = typer.Option(...),
    location: str = typer.Option(...),
    situation: str = typer.Option(...),
    dry_run: bool = typer.Option(False),
) -> None:
    """Initialize a persistent world."""
    try:
        models, settings = load_configs()
        slugs, place = validate_input(characters, location)
    except (ConfigError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None
    run_dir = create_run(slugs, place, situation, "initializer", settings.default_stop,
                         None, models, status="dry_run" if dry_run else "running")
    trace = TraceWriter(run_dir)
    trace.write("run_started", run_id=run_dir.name, mode="initializer")
    (run_dir / "retrieval.jsonl").touch()
    if dry_run:
        trace.write("run_finished", status="dry_run")
        typer.echo(run_dir)
        return
    stage = "scene_context"
    world_dir = None
    try:
        trace.write("stage_started", stage=stage, agent="initializer")
        asyncio.run(scene_context(Path.cwd(), run_dir, slugs, place, situation,
                                  models.initializer, settings.scene_context_max_turns, trace))
        trace.write("stage_finished", stage=stage)
        stage = "initializer_state"
        trace.write("stage_started", stage=stage, agent="initializer")
        state = asyncio.run(starting_state(Path.cwd(), run_dir, slugs, place, situation,
                                          models.initializer, settings.scene_context_max_turns, trace))
        trace.write("stage_finished", stage=stage)
        world_dir = create_world(slugs, place, situation, state, init_run_id=run_dir.name)
        (world_dir / "scene_context.md").write_bytes((run_dir / "scene_context.md").read_bytes())
        finish_run(run_dir, "passed")
    except Exception as error:
        if world_dir is not None:
            import shutil
            shutil.rmtree(world_dir)
        detail = str(error) if isinstance(error, SessionError) else type(error).__name__
        summary = f"{stage} failed: {detail}"
        finish_run(run_dir, "failed", summary)
        trace.write("stage_failed", stage=stage, error=summary)
        trace.write("run_finished", status="failed")
        typer.echo(f"{run_dir}: {summary}", err=True)
        raise typer.Exit(code=1) from None
    trace.write("run_finished", status="passed", world_id=world_dir.name)
    typer.echo(world_dir)
