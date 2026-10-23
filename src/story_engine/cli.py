import json
import asyncio
from pathlib import Path

import typer
from typing import Literal

from pydantic import ValidationError

from story_engine.config import ConfigError, load_configs
from story_engine.eval.pack import pack_runs
from story_engine.eval.suite import run_suite
from story_engine.kb import validate_input
from story_engine.agents.baseline import baseline_writer
from story_engine.agents.initializer import scene_context, starting_state
from story_engine.world.io import create_world
from story_engine.agents.sdk import SessionError
from story_engine.runs import RunInput, RunMeta, create_run, finish_run, read_scene_context
from story_engine.trace import TraceWriter

app = typer.Typer(help="Generate Octopath Traveler II stories.")
kb_app = typer.Typer(help="Build and check the knowledge base.")
eval_app = typer.Typer(help="Evaluate generated stories.")


@app.command()
def generate(
    characters: str = typer.Option(..., help="Comma-separated character slugs"),
    location: str = typer.Option(...),
    scenario: str = typer.Option(...),
    mode: Literal["baseline"] = typer.Option(...),
    stop_after: Literal["scene_context"] | None = typer.Option(None),
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
        character_slugs, location_slug = validate_input(characters, location)
    except ValueError as error:
        typer.echo(str(error), err=True)
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
            character_slugs, location_slug, scenario, mode, stop_after,
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
                story = (run_dir / "story.md").read_bytes()
                trace.write("stage_finished", stage=stage, word_count=len(story.decode("utf-8").split()))
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
    mode: Literal["baseline", "simulation"] = typer.Option(...),
    models_file: Path = typer.Option(Path("config/models.yaml"), "--models", help="Models YAML file"),
    dry_run: bool = typer.Option(False),
) -> None:
    """Run every case in eval/test_suite.yaml."""
    try:
        _, settings = load_configs(models_file)
        manifest, path = run_suite(models_file, dry_run, settings.suite_parallel, mode)
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
    run_dir = create_run(slugs, place, situation, "initializer",
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


@world_app.command("run")
def world_run(
    world_id: str = typer.Argument(...),
    stop_after: Literal["day", "curate"] | None = typer.Option(None),
    dry_run: bool = typer.Option(False),
) -> None:
    """Simulate through the current day's night, then curate and narrate one story."""
    from story_engine.simulation import CostCapReached, run_day
    from story_engine.world.io import load_state, read_events
    from story_engine.world.models import WorldInfo

    try:
        if Path(world_id).name != world_id or world_id in ("", ".", ".."):
            raise ValueError("world_id must be a world ID")
        world_dir = Path("worlds") / world_id
        state = load_state(world_dir)
        info = WorldInfo.model_validate_json((world_dir / "world.json").read_bytes())
        read_events(world_dir)
        context = (world_dir / "scene_context.md").read_bytes()
        models, settings = load_configs()
    except (OSError, ValueError, ConfigError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None
    run_dir = create_run(info.characters, info.location, info.situation, "simulation",
                         stop_after, models, status="dry_run" if dry_run else "running",
                         world_id=world_id, day=state.clock.day)
    trace = TraceWriter(run_dir)
    trace.write("run_started", run_id=run_dir.name, mode="simulation",
                world_id=world_id, day=state.clock.day)
    (run_dir / "retrieval.jsonl").touch()
    (run_dir / "scene_context.md").write_bytes(context)
    if dry_run:
        trace.write("run_finished", status="dry_run")
        typer.echo(run_dir)
        return
    stage = "day"
    try:
        trace.write("stage_started", stage="day")
        asyncio.run(run_day(world_dir, run_dir))
        trace.write("stage_finished", stage="day")
        if stop_after == "day":
            status = "stopped"
        else:
            stage = "curate"
            episode = _curate_day(world_dir, run_dir, state.clock.day, info, models, trace)
            if stop_after == "curate":
                status = "stopped"
            else:
                stage = "narrate"
                status = _narrate_acts(
                    world_dir, run_dir, state.clock.day, episode, info, models, settings, trace, 1, None,
                )
        finish_run(run_dir, status)
    except BaseException as error:
        status = "stopped" if isinstance(error, CostCapReached) else "failed"
        detail = str(error) if isinstance(error, (SessionError, CostCapReached)) else type(error).__name__
        reason = f"{stage} stopped: {detail}" if status == "stopped" else f"{stage} failed: {detail}"
        finish_run(run_dir, status, reason)
        trace.write("stage_failed", stage=stage, error=reason)
        trace.write("run_finished", status=status, error=reason)
        typer.echo(f"{run_dir}: {reason}", err=True)
        raise typer.Exit(code=1) from None
    trace.write("run_finished", status=status)
    typer.echo(run_dir)



def _curate_day(world_dir, run_dir, day, info, models, trace):
    from story_engine.agents.curator import curate
    from story_engine.world.io import read_events, read_scenes

    _, settings = load_configs()
    events = [event for event in read_events(world_dir) if event.day == day]
    scenes = [scene for scene in read_scenes(world_dir) if scene.day == day]
    trace.write("stage_started", stage="curate", agent="curator")
    episode = asyncio.run(curate(Path.cwd(), run_dir, events, scenes, info.characters,
                                 models.curator, settings.agent_max_turns, trace))
    trace.write("stage_finished", stage="curate")
    return episode


def _narrate_acts(world_dir, run_dir, day, episode, info, models, settings, trace,
                  start: int, stop_at: int | None):
    """Narrate acts `start` through `stop_at` (1-based, inclusive; None means to the end) of
    `episode`, writing acts/act_<n>.md. When the episode's last act is reached, also writes
    story.md. Returns 'stopped' or 'passed'."""
    from story_engine.agents.narrator import act_filename, narrate_act, strip_markers
    from story_engine.world.io import read_events, read_scenes

    events = [event for event in read_events(world_dir) if event.day == day]
    scenes = [scene for scene in read_scenes(world_dir) if scene.day == day]
    by_id = {scene.id: scene for scene in scenes}
    acts_dir = run_dir / "acts"
    total = len(episode.acts)
    last = total if stop_at is None else min(stop_at, total)
    previous_texts = [
        strip_markers((acts_dir / act_filename(number)).read_text(encoding="utf-8"))
        for number in range(1, start)
    ]
    for number in range(start, last + 1):
        act = episode.acts[number - 1]
        scene = by_id[act.scene]
        trace.write("stage_started", stage="narrate_act", agent="narrator", act=number)
        asyncio.run(narrate_act(
            Path.cwd(), run_dir, events, scenes, scene, act.pov, info.characters,
            models.narrator, settings.act_words, settings.writer_max_turns, trace,
            number, list(previous_texts),
        ))
        text = strip_markers((acts_dir / act_filename(number)).read_text(encoding="utf-8"))
        trace.write("stage_finished", stage="narrate_act", act=number, word_count=len(text.split()))
        previous_texts.append(text)
    if last == total:
        story = "\n\n---\n\n".join(previous_texts)
        (run_dir / "story.md").write_text(story, encoding="utf-8")
        return "passed"
    return "stopped"


def _narrate_act_debug(world_dir, run_dir, day, scene, pov, info, models, settings, trace):
    """The --act/--pov debugging path: narrate exactly one act, numbered 1, with no episode."""
    from story_engine.agents.narrator import narrate_act, strip_markers
    from story_engine.world.io import read_events, read_scenes

    events = [event for event in read_events(world_dir) if event.day == day]
    scenes = [other for other in read_scenes(world_dir) if other.day == day]
    trace.write("stage_started", stage="narrate_act", agent="narrator")
    asyncio.run(narrate_act(Path.cwd(), run_dir, events, scenes, scene, pov, info.characters,
                            models.narrator, settings.act_words, settings.writer_max_turns, trace,
                            1, []))
    draft = (run_dir / "acts" / "act_1.md").read_text(encoding="utf-8")
    trace.write("stage_finished", stage="narrate_act", word_count=len(strip_markers(draft).split()))


def _read_episode(episode_from: str, world_id: str):
    """Validate a source run and read its episode before reusing it, skipping the curator."""
    from story_engine.agents.curator import Episode

    if not episode_from or Path(episode_from).name != episode_from or episode_from in (".", ".."):
        raise ValueError("--episode-from must be a run ID")
    source = Path("runs") / episode_from
    try:
        # Read only the fields needed: older runs' meta may predate today's RunMeta schema.
        meta = json.loads((source / "meta.json").read_bytes())
        episode_bytes = (source / "episode.json").read_bytes()
    except (OSError, ValueError):
        raise ValueError(
            f"--episode-from {episode_from}: cannot read episode.json or meta.json"
        ) from None
    if meta.get("world_id") != world_id or meta.get("day") is None:
        raise ValueError(f"--episode-from {episode_from}: world_id or day differ")
    try:
        Episode.model_validate_json(episode_bytes)
    except ValidationError:
        raise ValueError(
            f"--episode-from {episode_from}: episode.json is in the old whole-episode format"
            " (expected {acts, why})"
        ) from None
    return int(meta["day"]), episode_bytes


def _parse_stop_after(value: str | None) -> tuple[str | None, int | None]:
    """Returns (kind, act_number): kind is None, 'curate', or 'act'."""
    if value is None or value == "curate":
        return value, None
    if value.startswith("act:"):
        try:
            number = int(value[len("act:"):])
        except ValueError:
            number = 0
        if number >= 1:
            return "act", number
    raise ValueError("--stop-after must be 'curate' or 'act:<n>' (n >= 1)")


def _existing_act_count(acts_dir: Path) -> int:
    from story_engine.agents.narrator import act_filename

    count = 0
    while (acts_dir / act_filename(count + 1)).exists():
        count += 1
    return count


@world_app.command("tell")
def world_tell(
    world_id: str = typer.Argument(...),
    day: int | None = typer.Option(None),
    stop_after: str | None = typer.Option(None, "--stop-after", help="'curate' or 'act:<n>'"),
    episode_from: str | None = typer.Option(
        None, "--episode-from", help="Reuse this run's episode.json, skipping the curator",
    ),
    continue_run: str | None = typer.Option(
        None, "--continue", help="Resume this stopped run, narrating its remaining acts",
    ),
    act: str | None = typer.Option(
        None, "--act", help="Narrate only this scene id as acts/act_1.md, skipping the curator",
    ),
    pov: str | None = typer.Option(None, "--pov", help="POV character for --act"),
) -> None:
    """Curate and narrate an episode from a completed day (latest by default)."""
    from story_engine.agents.curator import Episode
    from story_engine.world.io import load_state, read_events, read_scenes
    from story_engine.world.models import WorldInfo

    continue_run_dir = None
    episode = None
    start = 1
    reused_episode = None
    act_scene = None
    try:
        if Path(world_id).name != world_id or world_id in ("", ".", ".."):
            raise ValueError("world_id must be a world ID")
        if (act is None) != (pov is None):
            raise ValueError("--act and --pov must be given together")
        if act is not None and episode_from is not None:
            raise ValueError("--act cannot be combined with --episode-from")
        if act is not None and stop_after is not None:
            raise ValueError("--act cannot be combined with --stop-after")
        if act is not None and continue_run is not None:
            raise ValueError("--act cannot be combined with --continue")
        if continue_run is not None and (day is not None or episode_from is not None):
            raise ValueError("--continue cannot be combined with --day or --episode-from")
        stop_kind, stop_act = _parse_stop_after(stop_after)
        if continue_run is not None and stop_kind == "curate":
            raise ValueError("--continue cannot be combined with --stop-after curate")
        world_dir = Path("worlds") / world_id
        info = WorldInfo.model_validate_json((world_dir / "world.json").read_bytes())
        models, settings = load_configs()

        if continue_run is not None:
            if Path(continue_run).name != continue_run or continue_run in ("", ".", ".."):
                raise ValueError("--continue must be a run ID")
            continue_run_dir = Path("runs") / continue_run
            try:
                meta = RunMeta.model_validate_json((continue_run_dir / "meta.json").read_bytes())
                episode = Episode.model_validate_json((continue_run_dir / "episode.json").read_bytes())
            except (OSError, ValueError):
                raise ValueError(
                    f"--continue {continue_run}: cannot read episode.json or meta.json"
                ) from None
            if meta.world_id != world_id or meta.mode != "simulation" or meta.day is None:
                raise ValueError(f"--continue {continue_run}: world_id or day differ")
            if meta.status not in ("stopped", "failed"):
                # A failed act leaves the earlier acts intact, so the run can resume at it.
                raise ValueError(f"--continue {continue_run}: run is not stopped or failed")
            day = meta.day
            start = _existing_act_count(continue_run_dir / "acts") + 1
            if start > len(episode.acts):
                raise ValueError(f"--continue {continue_run}: all acts are already narrated")
        elif episode_from is not None:
            if day is not None:
                raise ValueError("--day cannot be combined with --episode-from")
            day, episode_bytes = _read_episode(episode_from, world_id)
            reused_episode = episode_bytes
        else:
            state = load_state(world_dir)
            day = state.clock.day - 1 if day is None else day
            if day >= state.clock.day:
                raise ValueError(f"Day {day} is not yet completed (current day: {state.clock.day})")
            if not any(event.day == day for event in read_events(world_dir)):
                raise ValueError(f"Day {day} has no events to curate")
            day_scenes = [scene for scene in read_scenes(world_dir) if scene.day == day]
            if not day_scenes:
                raise ValueError(f"Day {day} has no scene records")
            if act is not None:
                matches = [scene for scene in day_scenes if scene.id == act]
                if not matches:
                    raise ValueError(f"--act {act}: no such scene for day {day}")
                act_scene = matches[0]
                if pov not in act_scene.participants:
                    raise ValueError(f"--pov {pov}: not a participant of scene {act}")
        context = (world_dir / "scene_context.md").read_bytes()
    except (OSError, ValueError, ConfigError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from None

    if continue_run_dir is not None:
        run_dir = continue_run_dir
        trace = TraceWriter(run_dir)
        stage = "narrate"
        try:
            status = _narrate_acts(world_dir, run_dir, day, episode, info, models, settings, trace,
                                   start, stop_act)
            finish_run(run_dir, status)
        except Exception as error:
            detail = str(error) if isinstance(error, SessionError) else type(error).__name__
            reason = f"{stage} failed: {detail}"
            finish_run(run_dir, "failed", reason)
            trace.write("stage_failed", stage=stage, error=reason)
            trace.write("run_finished", status="failed", error=reason)
            typer.echo(f"{run_dir}: {reason}", err=True)
            raise typer.Exit(code=1) from None
        trace.write("run_finished", status=status)
        typer.echo(run_dir)
        return

    run_dir = create_run(info.characters, info.location, info.situation, "simulation",
                         stop_after, models, status="running", world_id=world_id, day=day)
    trace = TraceWriter(run_dir)
    trace.write("run_started", run_id=run_dir.name, mode="simulation", world_id=world_id, day=day)
    (run_dir / "scene_context.md").write_bytes(context)
    (run_dir / "retrieval.jsonl").touch()
    if act_scene is not None:
        stage = "narrate_act"
        try:
            _narrate_act_debug(world_dir, run_dir, day, act_scene, pov, info, models, settings, trace)
            finish_run(run_dir, "passed")
        except Exception as error:
            detail = str(error) if isinstance(error, SessionError) else type(error).__name__
            reason = f"{stage} failed: {detail}"
            finish_run(run_dir, "failed", reason)
            trace.write("stage_failed", stage=stage, error=reason)
            trace.write("run_finished", status="failed", error=reason)
            typer.echo(f"{run_dir}: {reason}", err=True)
            raise typer.Exit(code=1) from None
        trace.write("run_finished", status="passed")
        typer.echo(run_dir)
        return
    stage = "curate"
    try:
        if reused_episode is not None:
            (run_dir / "episode.json").write_bytes(reused_episode)
            trace.write("stage_reused", stage=stage, episode_from=episode_from)
            episode = Episode.model_validate_json(reused_episode)
        else:
            episode = _curate_day(world_dir, run_dir, day, info, models, trace)
        if stop_kind == "curate":
            status = "stopped"
        else:
            stage = "narrate"
            status = _narrate_acts(world_dir, run_dir, day, episode, info, models, settings, trace,
                                   1, stop_act)
        finish_run(run_dir, status)
    except Exception as error:
        detail = str(error) if isinstance(error, SessionError) else type(error).__name__
        reason = f"{stage} failed: {detail}"
        finish_run(run_dir, "failed", reason)
        trace.write("stage_failed", stage=stage, error=reason)
        trace.write("run_finished", status="failed", error=reason)
        typer.echo(f"{run_dir}: {reason}", err=True)
        raise typer.Exit(code=1) from None
    trace.write("run_finished", status=status)
    typer.echo(run_dir)


@eval_app.command('world')
def eval_world(
    world_ids: list[str] = typer.Argument(..., help='World IDs to evaluate sequentially'),
    day: int | None = typer.Option(None, min=1, help='Day for every world (default: latest or unfinished)'),
) -> None:
    """Evaluate world-day data and semantic consistency without changing worlds."""
    from story_engine.eval.world import evaluate_world, summary

    failed = False
    for world_id in world_ids:
        try:
            run_dir, report = asyncio.run(evaluate_world(world_id, day))
            typer.echo(summary(run_dir, report))
            failed |= report.judge_status == 'failed'
            if report.error:
                typer.echo(report.error, err=True)
        except (OSError, ValueError, ConfigError) as error:
            typer.echo(f'{world_id}: {error}', err=True)
            failed = True
    if failed:
        raise typer.Exit(code=1)
