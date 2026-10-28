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
    assert "osvald, temenos" in html and "montwise" in html
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
    assert "osvald, temenos" in response.text and "montwise" in response.text
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
