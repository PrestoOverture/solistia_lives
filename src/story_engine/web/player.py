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
    audio_url: str | None = None


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
                              hidden=event.actor == "world",
                              audio_url=f'/world/{directory.name}/audio/{event.id}.mp3' if actor else None).model_dump())
    return beats


def audio_file(worlds_dir: Path, world_id: str, event_id: str) -> Path | None:
    if not valid_id(world_id) or re.fullmatch(r'[0-9]+', event_id) is None:
        return None
    directory = worlds_dir / world_id
    audio = directory / 'audio'
    path = audio / f'{event_id}.mp3'
    if (directory.is_symlink() or audio.is_symlink() or path.is_symlink()
            or path.resolve().parent != worlds_dir / world_id / 'audio'):
        return None
    return path if path.is_file() else None
