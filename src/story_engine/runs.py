import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

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
    status: Literal["dry_run", "running", "passed", "failed"]


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
        status="dry_run",
    )
    run_dir = Path("runs") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "meta.json").write_text(
        json.dumps(meta.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return run_dir
