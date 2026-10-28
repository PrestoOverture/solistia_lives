"""Read-only story library; no agent sessions or model calls."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import markdown
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from story_engine.runs import RunInput


class _Metadata(BaseModel):
    created_at: datetime
    input: RunInput
    mode: str
    status: str


@dataclass
class Story:
    run_id: str
    title: str
    travelers: list[str]
    location: str
    word_count: int
    created_at: datetime
    text: str


def _read_story(runs_dir: Path, run_id: str) -> Story | None:
    if run_id in (".", "..") or Path(run_id).name != run_id:
        return None
    run_dir = runs_dir / run_id
    if run_dir.resolve().parent != runs_dir:
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
    """Serve stories from a directory, resolved once when the server starts."""
    runs_dir = runs_dir.resolve()
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

    @app.get("/", response_class=HTMLResponse)
    def library(request: Request):
        stories = [story for path in runs_dir.glob("*") if path.is_dir()
                   if (story := _read_story(runs_dir, path.name)) is not None]
        stories.sort(key=lambda story: (story.created_at, story.run_id), reverse=True)
        return templates.TemplateResponse(request=request, name="library.html", context={"stories": stories})

    @app.get("/story/{run_id}", response_class=HTMLResponse)
    def story(request: Request, run_id: str):
        item = _read_story(runs_dir, run_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Story not found")
        return templates.TemplateResponse(request=request, name="story.html", context={
            "story": item, "content": markdown.markdown(item.text),
        })

    return app
