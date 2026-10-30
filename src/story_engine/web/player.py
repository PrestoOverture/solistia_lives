"""Read-only scene-player data from world artifacts."""

import re
import hashlib
from pathlib import Path

import yaml

from pydantic import BaseModel, Field

from story_engine.stages import StandPoint, StageSpot, StageCatalog, load_catalog
from story_engine.kb import TRAVELERS
from story_engine.world.voice import read_people
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
    departed: list[str] = Field(default_factory=list)


def scene_beats(directory: Path, scene_id: str, names: dict[str, str]) -> list[dict]:
    beats = []
    departed = []
    for event in sorted(read_events(directory), key=lambda event: event.id):
        if event.scene != scene_id:
            continue
        if event.move == "leave" and event.actor not in departed:
            departed.append(event.actor)
        fields = []
        if event.action:
            fields.append((event.action, None, '.action.mp3'))
        if event.say:
            fields.append((event.say, event.actor, '.mp3'))
        if not fields:
            fields.append((event.content, None, None))
        for text, actor, suffix in fields:
            beats.append(Beat(event_id=event.id, text=text, actor=actor, departed=list(departed),
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
    stand_ins: dict[str, str] = {}
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
    for slug, filename in list(art.sprites.items()):
        if asset_file(directory, filename) is None:
            del art.sprites[slug]
    return art


class SceneStage(BaseModel):
    image: str | None = None
    darken: bool = False
    stand: list[StandPoint] = Field(default_factory=list)


def scene_stage(directory: Path, place: str, spot: str | None, part: str,
                art: PlayerArt) -> SceneStage:
    catalog = load_catalog(directory, place)
    if catalog is None:
        target = art.stand_ins.get(place, "").split("/")
        if len(target) != 2:
            return SceneStage()
        place, spot = target
        catalog = load_catalog(directory, place)
    if catalog is None:
        return SceneStage()
    selected = next((item for item in catalog.spots if item.id == spot), None)
    if selected is None:
        selected = next((item for item in catalog.spots if item.id == catalog.default), None)
    if selected is None:
        return SceneStage()
    images = {time: f"clean/{place}/{filename}" for time in ("day", "night")
              if (filename := getattr(selected, time))
              and asset_file(directory / "clean" / place, filename) is not None}
    night = part in {"evening", "night"}
    image = images.get("night" if night else "day") or images.get("day" if night else "night")
    return SceneStage(image=image, darken=bool(night and "night" not in images and image),
                      stand=selected.stand if image else [])


def stand_points(points: list[StandPoint], count: int) -> list[StandPoint]:
    """Keep catalog order, staggering each overflow row slightly to the right."""
    if not points:
        return []
    result = []
    for i in range(count):
        point = points[i % len(points)]
        result.append(point.model_copy(update={"x": min(1.0, point.x + .025 * (i // len(points)))}))
    return result


def stage_images(directory: Path) -> set[str]:
    """Only catalog-listed clean images may be served, alongside manifest sprites."""
    images = set()
    for path in (directory / "stages").glob("*.yaml"):
        catalog = load_catalog(directory, path.stem)
        if catalog:
            for spot in catalog.spots:
                for filename in (spot.day, spot.night):
                    if filename and asset_file(directory / "clean" / path.stem, filename):
                        images.add(f"clean/{path.stem}/{filename}")
    return images


def town_sprites(directory: Path) -> dict[str, list[str]]:
    pools = {'m': [], 'f': []}
    try:
        data = yaml.safe_load((directory / 'sprites/index.yaml').read_text())
    except FileNotFoundError:
        return pools
    for item in data['sprites']:
        if item.get('who') == 'townsperson' and item.get('view') == 'front' and item.get('sex') in pools:
            filename = 'sprites/' + item['file']
            if Path(filename).suffix.lower() == '.png' and asset_file(directory, filename):
                pools[item['sex']].append(filename)
    return pools


def scene_sprites(directory: Path, world_dir: Path, participants: list[str], art: PlayerArt) -> dict[str, str | None]:
    pools = town_sprites(directory)
    people = read_people(world_dir)
    result = {name: art.sprites.get(name) for name in participants if name in TRAVELERS}
    used = set()
    # Known-sex people reserve their smaller pools before unknown-sex people.
    minors = [name for name in participants if name not in TRAVELERS]
    for name in sorted(minors, key=lambda name: (name not in people or people[name].sex is None, name)):
        sex = people[name].sex if name in people else None
        pool = pools[sex] if sex in pools else pools['m'] + pools['f']
        if not pool:
            result[name] = None
            continue
        number = int.from_bytes(hashlib.sha256(name.encode('utf-8')).digest(), 'big')
        choices = pool[number % len(pool):] + pool[:number % len(pool)]
        chosen = next((filename for filename in choices if filename not in used), choices[0])
        result[name] = chosen
        used.add(chosen)
    return result
