import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.web import create_app


def write_run(runs: Path, run_id: str, *, mode: str = "baseline", status: str = "passed",
              story: str | None = "# First title\n\nA quiet **afternoon**.\n\nAnother paragraph.",
              created_at: str = "2026-10-27T08:00:00+00:00") -> None:
    run = runs / run_id
    run.mkdir(parents=True)
    (run / "meta.json").write_text(json.dumps({
        "mode": mode, "status": status, "created_at": created_at,
        "input": {"characters": ["osvald", "temenos"], "location": "montwise", "scenario": "A visit"},
    }), encoding="utf-8")
    if story is not None:
        (run / "story.md").write_text(story, encoding="utf-8")


def test_library_filters_and_orders_runs(tmp_path):
    runs = tmp_path / "runs"
    write_run(runs, "older")
    write_run(runs, "newer", created_at="2026-10-28T09:00:00+01:00", story="# New title\n\nNew prose.")
    for status in ("failed", "running", "stopped", "dry_run"):
        write_run(runs, status, status=status)
    write_run(runs, "simulation", mode="simulation")
    write_run(runs, "missing-story", story=None)
    (runs / "bad-meta").mkdir()
    (runs / "bad-meta" / "meta.json").write_text("{", encoding="utf-8")

    with TestClient(create_app(runs)) as client:
        response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert html.count('/story/') == 2
    assert html.index('/story/newer') < html.index('/story/older')
    assert "New title" in html and "First title" in html
    assert "Osvald V. Vanstein, Temenos Mistral" in html and "Montwise" in html
    assert 'href="http://testserver/new"' in html
    assert "8 words" in html and "2026-10-28" in html
    assert 'hx-boost="true"' in html and 'https://cdn.jsdelivr.net/npm/htmx.org@' in html


def test_story_renders_markdown_and_header(tmp_path):
    write_run(tmp_path, "passed")
    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/story/passed")
        boosted = client.get("/story/passed", headers={"HX-Request": "true"})
    assert response.status_code == boosted.status_code == 200
    assert "<h1>First title</h1>" in response.text
    assert "<p>A quiet <strong>afternoon</strong>.</p>" in response.text
    assert "<p>Another paragraph.</p>" in response.text
    assert "Osvald V. Vanstein, Temenos Mistral" in response.text and "Montwise" in response.text
    assert response.text.split("<body", 1)[1].count("First title") == 1
    assert "8 words" in response.text
    assert 'href="http://testserver/"' in response.text
    assert "max-width: 65ch" in response.text
    assert "prefers-color-scheme: dark" in response.text


@pytest.mark.parametrize("run_id,mode,status,story", [
    ("failed", "baseline", "failed", "# Failed story"),
    ("running", "baseline", "running", "# In progress"),
    ("simulation", "simulation", "passed", "# Simulation"),
    ("missing-story", "baseline", "passed", None),
    ("unknown", None, None, None),
])
def test_ineligible_story_returns_404(tmp_path, run_id, mode, status, story):
    if mode is not None:
        write_run(tmp_path, run_id, mode=mode, status=status, story=story)
    with TestClient(create_app(tmp_path)) as client:
        assert client.get(f"/story/{run_id}").status_code == 404


def test_empty_library_and_read_only_routes(tmp_path):
    with TestClient(create_app(tmp_path / "missing")) as client:
        assert "No passed stories yet." in client.get("/").text
        assert client.post("/").status_code == 405
        assert client.post("/story/unknown").status_code == 405
    assert not (tmp_path / "missing").exists()


def test_symlink_cannot_expose_runs_outside_library(tmp_path):
    write_run(tmp_path, "outside")
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "linked").symlink_to(tmp_path / "outside", target_is_directory=True)
    with TestClient(create_app(runs)) as client:
        assert '/story/linked' not in client.get("/").text
        assert client.get("/story/linked").status_code == 404


@pytest.mark.parametrize("options,port", [([], 8000), (["--port", "8123"], 8123)])
def test_web_cli_binds_localhost(monkeypatch, options, port):
    calls = []
    monkeypatch.setattr("uvicorn.run", lambda app, **kwargs: calls.append((app, kwargs)))
    result = CliRunner().invoke(app, ["web", *options])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0][1] == {"host": "127.0.0.1", "port": port}


def test_new_form_lists_all_travelers_and_locations(tmp_path):
    import frontmatter

    from story_engine.kb import TRAVELERS, location_slugs

    with TestClient(create_app(tmp_path)) as client:
        response = client.get("/new")
    assert response.status_code == 200
    assert response.text.count('type="checkbox"') == 8
    for slug in TRAVELERS:
        metadata = frontmatter.load(Path("kb/characters") / slug / f"{slug}.md")
        assert f'value="{slug}"' in response.text
        assert metadata["aliases"][0] in response.text
    for slug in location_slugs():
        assert f'<option value="{slug}">' in response.text
    assert ">Montwise</option>" in response.text
    assert 'name="situation"' in response.text
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("characters,location,message", [
    (["throne"], "montwise", "expected 2-3 distinct travelers"),
    (["throne", "agnea"], "unknown-place", "unknown location"),
    (["throne", "throne"], "montwise", "repeated traveler"),
    (["throne", "not-a-traveler"], "montwise", "unknown traveler"),
    (["throne", "agnea", "osvald", "temenos"], "montwise", "expected 2-3 distinct travelers"),
])
def test_invalid_form_starts_nothing(tmp_path, monkeypatch, characters, location, message):
    calls = []
    monkeypatch.setattr("story_engine.web.generate_story", lambda *args: calls.append(args))
    with TestClient(create_app(tmp_path)) as client:
        response = client.post("/new", data={
            "characters": characters, "location": location, "situation": "A quiet visit.",
        })
    assert response.status_code == 422
    assert message in response.text
    assert 'role="alert"' in response.text
    assert "A quiet visit." in response.text
    assert 'value="throne" checked' in response.text
    assert calls == []
    assert not list(tmp_path.iterdir())


def test_valid_form_starts_one_background_job_and_redirects(tmp_path, monkeypatch):
    from story_engine.runs import RunMeta

    calls = []
    monkeypatch.setattr("story_engine.web.generate_story", lambda *args: calls.append(args))
    with TestClient(create_app(tmp_path)) as client:
        response = client.post("/new", data={
            "characters": ["throne", "agnea"], "location": "montwise",
            "situation": "A quiet visit.",
        }, follow_redirects=False)
        assert response.status_code == 303
        assert len(calls) == 1
        run_dir, models, settings = calls[0]
        assert response.headers["location"] == f"http://testserver/run/{run_dir.name}"
        assert client.get(response.headers["location"]).status_code == 200
    meta = RunMeta.model_validate_json((run_dir / "meta.json").read_bytes())
    assert meta.input.characters == ["throne", "agnea"]
    assert meta.input.location == "montwise"
    assert meta.input.scenario == "A quiet visit."
    assert meta.mode == "baseline" and meta.status == "running"
    assert run_dir.parent == tmp_path.resolve()
    assert list(tmp_path.iterdir()) == [run_dir]
    assert not (run_dir / "story.md").exists()


@pytest.fixture
def traced_run(tmp_path):
    write_run(tmp_path, "progress", status="running", story=None)
    events = [
        {"type": "run_started", "ts": "2026-10-27T08:00:00+00:00"},
        {"type": "stage_started", "stage": "baseline_writer", "ts": "2026-10-27T08:00:01+00:00"},
        {"type": "stage_finished", "stage": "baseline_writer", "ts": "2026-10-27T08:01:00+00:00"},
        {"type": "stage_started", "stage": "validate", "ts": "2026-10-27T08:01:01+00:00"},
        {"type": "stage_usage", "stage": "extract", "ts": "2026-10-27T08:01:02+00:00"},
        {"type": "stage_finished", "stage": "validate", "ts": "2026-10-27T08:01:03+00:00"},
        {"type": "stage_started", "stage": "fix", "ts": "2026-10-27T08:01:04+00:00"},
        {"type": "stage_started", "stage": "validate", "ts": "2026-10-27T08:02:00+00:00"},
    ]
    run_dir = tmp_path / "progress"
    (run_dir / "trace.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events) + '{"type":',
        encoding="utf-8",
    )
    return run_dir


def test_run_progress_polls_and_passed_run_links_story(traced_run):
    from datetime import datetime, timezone

    from story_engine.web.progress import read_progress

    with TestClient(create_app(traced_run.parent)) as client:
        response = client.get("/run/progress")
        assert response.status_code == 200
        assert "Status: running" in response.text
        assert "Current stage: validate" in response.text
        assert "Validation round: 2" in response.text
        assert 'hx-trigger="every 3s"' in response.text
        fragment = client.get("/run/progress", headers={"HX-Request": "true", "HX-Target": "progress"})
        assert fragment.text.startswith('<section id="progress"')
        assert "<html" not in fragment.text
        trace = traced_run / "trace.jsonl"
        # Replace the partial write with a completed terminal event.
        trace.write_text(trace.read_text().rsplit("\n", 1)[0] + "\n" + json.dumps({
            "type": "run_finished", "status": "passed", "ts": "2026-10-27T08:02:30+00:00",
        }) + "\n")
        meta_path = traced_run / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta["status"] = "passed"
        meta_path.write_text(json.dumps(meta))
        (traced_run / "story.md").write_text("# Finished\n\nThe end.")
        response = client.get("/run/progress")
        assert 'href="http://testserver/story/progress"' in response.text
        assert "Elapsed: 150 seconds" in response.text
        assert "every 3s" not in response.text
        assert client.get("/story/progress").status_code == 200
    progress = read_progress(traced_run, datetime(2026, 10, 27, 8, tzinfo=timezone.utc))
    assert progress["elapsed"] == 150


def test_failed_run_shows_error_and_stops_polling(traced_run):
    path = traced_run / "meta.json"
    meta = json.loads(path.read_text())
    meta.update(status="failed", error="validate failed: contradictions remain")
    path.write_text(json.dumps(meta))
    with TestClient(create_app(traced_run.parent)) as client:
        response = client.get("/run/progress")
    assert "Status: failed" in response.text
    assert "validate failed: contradictions remain" in response.text
    assert "every 3s" not in response.text
    assert "/story/progress" not in response.text


def test_background_job_reuses_cli_pipeline(tmp_path, monkeypatch):
    from story_engine.config import load_configs
    from story_engine.runs import create_run, finish_run
    from story_engine.web.jobs import generate_story
    import typer

    models, settings = load_configs()
    run_dir = create_run(["throne", "agnea"], "montwise", "A visit", "baseline",
                         None, models, status="running", runs_dir=tmp_path)
    calls = []

    def fake_execute(*args):
        calls.append(args)
        finish_run(args[0], "failed", "Faked failure")
        raise typer.Exit(code=1)

    monkeypatch.setattr("story_engine.cli._execute_generate", fake_execute)
    generate_story(run_dir, models, settings)
    assert calls == [(run_dir, ["throne", "agnea"], "montwise", "A visit",
                      "baseline", None, models, settings)]
    assert json.loads((run_dir / "meta.json").read_text())["status"] == "failed"


def test_story_uses_accented_kb_display_name(tmp_path):
    write_run(tmp_path, "accent")
    path = tmp_path / "accent" / "meta.json"
    meta = json.loads(path.read_text())
    meta["input"]["characters"] = ["throne", "agnea"]
    path.write_text(json.dumps(meta))
    with TestClient(create_app(tmp_path)) as client:
        html = client.get("/story/accent").text
    assert "Throné Anguis, Agnea Bristarni" in html
    assert "Montwise" in html
    assert html.split("<body", 1)[1].count("First title") == 1


def test_progress_rejects_external_symlinks_and_unknown_runs(tmp_path):
    write_run(tmp_path, "outside")
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "linked").symlink_to(tmp_path / "outside", target_is_directory=True)
    write_run(runs, "trace-link", status="running")
    (runs / "trace-link" / "trace.jsonl").symlink_to(tmp_path / "outside" / "meta.json")
    with TestClient(create_app(runs)) as client:
        for name in ("unknown", "linked", "trace-link"):
            assert client.get(f"/run/{name}").status_code == 404
