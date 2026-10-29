"""Read-only scene-player data from world artifacts."""

import re
from pathlib import Path

from pydantic import BaseModel

from story_engine.world.io import read_events, read_scenes
from story_engine.world.models import SceneRecord, WorldInfo


def valid_id(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_-]+", value) is not None


def read_world(worlds_dir: Path, world_id: str) -> tuple[WorldInfo, list[SceneRecord]] | None:
    if not valid_id(world_id):
        return None
    directory = worlds_dir / world_id
    if directory.resolve().parent != worlds_dir:
        return None
    try:
        if any((directory / name).is_symlink() for name in
               ("world.json", "genesis.json", "scenes.jsonl", "events.jsonl")):
            return None
        if not (directory / "genesis.json").is_file():
            return None
        info = WorldInfo.model_validate_json((directory / "world.json").read_bytes())
        scenes = [scene for scene in read_scenes(directory) if valid_id(scene.id)]
    except (OSError, ValueError):
        return None
    return (info, scenes) if scenes else None


class Beat(BaseModel):
    event_id: int
    text: str
    speaker: str | None
    actor: str | None
    hidden: bool


def scene_beats(directory: Path, scene_id: str, names: dict[str, str]) -> list[dict]:
    beats = []
    for event in sorted(read_events(directory), key=lambda event: event.id):
        if event.scene != scene_id:
            continue
        fields = []
        if event.action:
            fields.append((event.action, None))
        if event.say:
            fields.append((event.say, event.actor))
        if not fields:
            fields.append((event.content, None))
        for text, actor in fields:
            beats.append(Beat(event_id=event.id, text=text, actor=actor,
                              speaker=names.get(actor, actor) if actor else None,
                              hidden=event.actor == "world").model_dump())
    return beats
