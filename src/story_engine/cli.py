import asyncio
from pathlib import Path

import typer
from typing import Literal

from story_engine.config import ConfigError, load_configs, valid_stop
from story_engine.kb import validate_input
from story_engine.agents.baseline import baseline_writer
from story_engine.agents.director import scene_context
from story_engine.agents.sdk import SessionError
from story_engine.runs import create_run, finish_run
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
) -> None:
    """Generate a story."""
    try:
        models, settings = load_configs()
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
    if dry_run:
        run_dir = create_run(
            character_slugs,
            location_slug,
            scenario,
            mode,
            resolved_stop,
            stop_after,
            models,
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
        )
        trace = TraceWriter(run_dir)
        trace.write("run_started", run_id=run_dir.name, mode=mode)
        stage = "scene_context"
        trace.write("stage_started", stage="scene_context", agent="director")
        try:
            asyncio.run(scene_context(
                Path.cwd(), run_dir, character_slugs, location_slug, scenario,
                models.director, settings.scene_context_max_turns, trace,
            ))
            trace.write("stage_finished", stage="scene_context")
            if stop_after == "scene_context":
                status = "stopped"
            else:
                stage = "baseline_writer"
                trace.write("stage_started", stage=stage, agent="baseline")
                asyncio.run(baseline_writer(
                    Path.cwd(), run_dir, character_slugs, location_slug, scenario,
                    models.baseline, settings.words, settings.turn_cap, trace,
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


app.add_typer(kb_app, name="kb")
app.add_typer(eval_app, name="eval")
