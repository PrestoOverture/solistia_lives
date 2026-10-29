"""Read-only scene-player data from world artifacts."""

import re
from pathlib import Path

import yaml

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
            fields.append((event.action, None, '.action.mp3'))
        if event.say:
            fields.append((event.say, event.actor, '.mp3'))
        if not fields:
            fields.append((event.content, None, None))
        for text, actor, suffix in fields:
            beats.append(Beat(event_id=event.id, text=text, actor=actor,
                              speaker=names.get(actor, actor) if actor else None,
                              hidden=event.actor == "world",
                              audio_url=f'/world/{directory.name}/audio/{event.id}{suffix}' if suffix else None).model_dump())
    return beats


def audio_file(worlds_dir: Path, world_id: str, event_id: str) -> Path | None:
    if not valid_id(world_id) or re.fullmatch(r'[0-9]+(?:\.action)?', event_id) is None:
        return None
    directory = worlds_dir / world_id
    audio = directory / 'audio'
    path = audio / f'{event_id}.mp3'
    if (directory.is_symlink() or audio.is_symlink() or path.is_symlink()
            or path.resolve().parent != worlds_dir / world_id / 'audio'):
        return None
    return path if path.is_file() else None


class PlayerArt(BaseModel):
    backdrops: dict[str, str] = {}
    sprites: dict[str, str] = {}


def asset_file(directory: Path, filename: str) -> Path | None:
    """Resolve only local image paths, including through symlinks."""
    if "\\" in filename or Path(filename).is_absolute():
        return None
    try:
        path = (directory / filename).resolve()
        if (not path.is_relative_to(directory.resolve())
                or path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}
                or not path.is_file()):
            return None
    except (OSError, ValueError, RuntimeError):
        return None
    return path


def load_art(directory: Path) -> PlayerArt:
    """Missing local art keeps the P2 placeholders usable in public checkouts."""
    try:
        art = PlayerArt.model_validate(yaml.safe_load((directory / "manifest.yaml").read_text()))
    except (OSError, ValueError, yaml.YAMLError):
        return PlayerArt()
    for mapping in (art.backdrops, art.sprites):
        for slug, filename in list(mapping.items()):
            if asset_file(directory, filename) is None:
                del mapping[slug]
    return art
