import typer
from typing import Literal

from story_engine.config import ConfigError, load_configs, valid_stop
from story_engine.runs import create_run
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
    if dry_run:
        run_dir = create_run(
            [character.strip() for character in characters.split(",")],
            location,
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
