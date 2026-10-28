"""Localhost story library and background baseline generation."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs

import frontmatter

import markdown
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from story_engine.config import ConfigError, load_configs
from story_engine.kb import TRAVELERS, validate_input
from story_engine.runs import RunInput, create_run
from story_engine.web.jobs import generate_story
from story_engine.web.progress import read_progress


class _Metadata(BaseModel):
    created_at: datetime
    input: RunInput
    mode: str
    status: str
    error: str | None = None


@dataclass
class Story:
    run_id: str
    title: str
    travelers: list[str]
    location: str
    word_count: int
    created_at: datetime
    text: str


def _display_name(path: Path) -> str:
    metadata = frontmatter.load(path)
    name = metadata.get("name", path.stem)
    return (metadata.get("aliases") or [name])[0] if name == path.stem else name


def _run_dir(runs_dir: Path, run_id: str) -> Path | None:
    if run_id in (".", "..") or Path(run_id).name != run_id:
        return None
    run_dir = runs_dir / run_id
    if run_dir.resolve().parent != runs_dir:
        return None
    return run_dir


def _read_story(runs_dir: Path, run_id: str) -> Story | None:
    run_dir = _run_dir(runs_dir, run_id)
    if run_dir is None:
        return None
    try:
        # Only the public story and metadata may be read, never arbitrary run files.
        if any((run_dir / name).is_symlink() for name in ("meta.json", "story.md")):
            return None
        meta = _Metadata.model_validate_json((run_dir / "meta.json").read_bytes())
        if meta.mode != "baseline" or meta.status != "passed":
            return None
        text = (run_dir / "story.md").read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    title = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), run_id)
    created_at = meta.created_at.replace(tzinfo=meta.created_at.tzinfo or timezone.utc)
    return Story(run_id, title, meta.input.characters, meta.input.location,
                 len(text.split()), created_at, text)


def create_app(runs_dir: Path = Path("runs")) -> FastAPI:
    """Serve stories and start baseline jobs in the given run directory."""
    runs_dir = runs_dir.resolve()
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    travelers = {slug: _display_name(Path("kb/characters") / slug / f"{slug}.md")
                 for slug in sorted(TRAVELERS)}
    locations = {path.stem: _display_name(path) for path in Path("kb/locations").rglob("*.md")}
    locations = dict(sorted(locations.items(), key=lambda item: item[1]))

    def display_story(item):
        item.travelers = [travelers.get(slug, slug) for slug in item.travelers]
        item.location = locations.get(item.location, item.location)
        return item

    templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

    @app.get("/", response_class=HTMLResponse)
    def library(request: Request):
        stories = [display_story(story) for path in runs_dir.glob("*") if path.is_dir()
                   if (story := _read_story(runs_dir, path.name)) is not None]
        stories.sort(key=lambda story: (story.created_at, story.run_id), reverse=True)
        return templates.TemplateResponse(request=request, name="library.html", context={"stories": stories})

    @app.get("/story/{run_id}", response_class=HTMLResponse)
    def story(request: Request, run_id: str):
        item = _read_story(runs_dir, run_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Story not found")
        # The page header carries the first Markdown title.
        lines = item.text.splitlines(keepends=True)
        for index, line in enumerate(lines):
            if line.startswith("# "):
                del lines[index]
                break
        return templates.TemplateResponse(request=request, name="story.html", context={
            "story": display_story(item), "content": markdown.markdown("".join(lines)),
        })

    def form(request, *, selected=(), location="", situation="", error=None, status_code=200):
        return templates.TemplateResponse(request=request, name="new.html", status_code=status_code,
            context=dict(travelers=travelers, locations=locations, selected=selected,
                         location=location, situation=situation, error=error))

    @app.get("/new", response_class=HTMLResponse)
    def new_story(request: Request):
        return form(request)

    @app.post("/new", response_class=HTMLResponse)
    async def submit_story(request: Request, background_tasks: BackgroundTasks):
        # Native HTML forms use urlencoding; no multipart dependency is needed.
        fields = parse_qs((await request.body()).decode("utf-8"), keep_blank_values=True)
        selected = fields.get("characters", [])
        location = fields.get("location", [""])[0]
        situation = fields.get("situation", [""])[0]
        try:
            characters, place = validate_input(",".join(selected), location)
            models, settings = load_configs()
        except (ValueError, ConfigError) as error:
            return form(request, selected=selected, location=location, situation=situation,
                        error=str(error), status_code=422)
        run_dir = create_run(characters, place, situation, "baseline", None, models,
                             status="running", runs_dir=runs_dir)
        background_tasks.add_task(generate_story, run_dir, models, settings)
        return RedirectResponse(request.url_for("run", run_id=run_dir.name), status_code=303)

    @app.get("/run/{run_id}", response_class=HTMLResponse)
    def run(request: Request, run_id: str):
        run_dir = _run_dir(runs_dir, run_id)
        if run_dir is None or any((run_dir / name).is_symlink()
                                  for name in ("meta.json", "trace.jsonl")):
            raise HTTPException(status_code=404, detail="Run not found")
        try:
            meta = _Metadata.model_validate_json((run_dir / "meta.json").read_bytes())
        except (OSError, ValueError):
            raise HTTPException(status_code=404, detail="Run not found") from None
        if meta.mode != "baseline":
            raise HTTPException(status_code=404, detail="Run not found")
        progress = read_progress(run_dir, meta.created_at)
        context = dict(run_id=run_id, meta=meta, progress=progress)
        name = "progress.html" if request.headers.get("HX-Target") == "progress" else "run.html"
        return templates.TemplateResponse(request=request, name=name, context=context)

    return app
