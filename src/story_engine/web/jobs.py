"""Run the CLI's prepared baseline pipeline after the response is sent."""

import typer

from story_engine.runs import RunMeta


def generate_story(run_dir, models, settings):
    from story_engine.cli import _execute_generate

    meta = RunMeta.model_validate_json((run_dir / "meta.json").read_bytes())
    try:
        _execute_generate(
            run_dir, meta.input.characters, meta.input.location, meta.input.scenario,
            "baseline", None, models, settings,
        )
    except typer.Exit:
        # The shared pipeline has already persisted the failure and its trace.
        pass
