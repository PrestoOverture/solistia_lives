import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel

from story_engine.config import Models


class RunInput(BaseModel):
    characters: list[str]
    location: str
    scenario: str


class RunMeta(BaseModel):
    run_id: str
    created_at: str
    input: RunInput
    mode: Literal["pipeline", "baseline"]
    stop: str
    stop_after: Literal["scene_context", "beat_plan", "transcript"] | None
    models: Models
    prompt_hashes: dict[str, str]
    status: Literal["dry_run", "running", "passed", "failed", "stopped"]
    api_host: str = "api.anthropic.com"
    error: str | None = None


def _prompt_hashes() -> dict[str, str]:
    hashes = {}
    for directory in (Path("prompts"), Path("cards")):
        for path in directory.rglob("*"):
            if any(part.startswith(".") for part in path.parts) or not path.is_file():
                continue
            hashes[path.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(hashes.items()))


def create_run(
    characters: list[str],
    location: str,
    scenario: str,
    mode: Literal["pipeline", "baseline"],
    stop: str,
    stop_after: Literal["scene_context", "beat_plan", "transcript"] | None,
    models: Models,
    status: Literal["dry_run", "running"] = "dry_run",
) -> Path:
    now = datetime.now(timezone.utc)
    run_id = f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
    meta = RunMeta(
        run_id=run_id,
        created_at=now.isoformat(),
        input=RunInput(characters=characters, location=location, scenario=scenario),
        mode=mode,
        stop=stop,
        stop_after=stop_after,
        models=models,
        prompt_hashes=_prompt_hashes(),
        status=status,
    )
    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "meta.json").write_text(
        json.dumps(meta.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir


def record_api_host(run_dir: Path, base_url: str | None) -> None:
    """Record only the host from the effective session URL, never credentials."""
    path = run_dir / "meta.json"
    meta = RunMeta.model_validate_json(path.read_text(encoding="utf-8"))
    meta.api_host = urlsplit(base_url or "https://api.anthropic.com").hostname or "api.anthropic.com"
    path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")


def finish_run(run_dir: Path, status: Literal["stopped", "passed", "failed"], error: str | None = None) -> None:
    path = run_dir / "meta.json"
    meta = RunMeta.model_validate_json(path.read_text(encoding="utf-8"))
    meta.status = status
    meta.error = error
    path.write_text(meta.model_dump_json(indent=2), encoding="utf-8")
