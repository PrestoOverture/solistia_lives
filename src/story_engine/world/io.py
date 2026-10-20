"""Path-based storage for worlds; no agent or model calls."""

import json
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .models import Event, WorldInfo, WorldState


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object)


def _atomic_write(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _validate_state(info: WorldInfo, state: WorldState) -> WorldState:
    # Revalidate even model instances: callers may have mutated nested containers.
    state = WorldState.model_validate(state.model_dump())
    if set(state.characters) != set(info.characters):
        raise ValueError("state characters must match world.json exactly")
    return state


def create_world(
    characters: list[str],
    location: str,
    situation: str,
    state: WorldState,
    *,
    worlds_dir: Path = Path("worlds"),
    init_run_id: str | None = None,
) -> Path:
    """Create a world with an already initialized state and return its directory."""
    now = datetime.now(timezone.utc)
    info = WorldInfo(characters=characters, location=location, situation=situation,
                     created_at=now.isoformat(), init_run_id=init_run_id)
    state = _validate_state(info, state)
    world_id = f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
    world_dir = worlds_dir / world_id
    world_dir.mkdir(parents=True, exist_ok=False)
    (world_dir / "memory").mkdir()
    _atomic_write(world_dir / "world.json", info.model_dump_json(indent=2))
    _atomic_write(world_dir / "state.json", state.model_dump_json(indent=2))
    (world_dir / "events.jsonl").touch()
    return world_dir


def load_state(world_dir: Path) -> WorldState:
    info = WorldInfo.model_validate(_read_json(world_dir / "world.json"))
    return _validate_state(info, WorldState.model_validate(_read_json(world_dir / "state.json")))


def validate_state(world_dir: Path, state: WorldState) -> WorldState:
    """Validate a proposed state against the persistent world without writing it."""
    info = WorldInfo.model_validate(_read_json(world_dir / "world.json"))
    return _validate_state(info, state)


def save_state(world_dir: Path, state: WorldState) -> None:
    info = WorldInfo.model_validate(_read_json(world_dir / "world.json"))
    state = _validate_state(info, state)
    _atomic_write(world_dir / "state.json", state.model_dump_json(indent=2))


def read_events(world_dir: Path) -> list[Event]:
    events = []
    with (world_dir / "events.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            event = Event.model_validate_json(line)
            if events and event.id <= events[-1].id:
                raise ValueError("event ids must be strictly increasing")
            events.append(event)
    return events


def append_event(world_dir: Path, event: Event) -> Event:
    """Assign the next persisted ID and append. World writes are sequential."""
    events = read_events(world_dir)
    data = event.model_dump()
    data["id"] = events[-1].id + 1 if events else 1
    event = Event.model_validate(data)
    info = WorldInfo.model_validate(_read_json(world_dir / "world.json"))
    if event.intent is not None and event.actor not in info.characters:
        raise ValueError("only main characters may have private intent")
    with (world_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(event.model_dump_json() + "\n")
    return event


def _memory_path(world_dir: Path, character: str) -> Path:
    info = WorldInfo.model_validate(_read_json(world_dir / "world.json"))
    if (character not in info.characters or not character
            or Path(character).name != character or character in (".", "..")):
        raise ValueError("memory character must be a main character name")
    return world_dir / "memory" / f"{character}.md"


def read_memory(world_dir: Path, character: str) -> str:
    return _memory_path(world_dir, character).read_text(encoding="utf-8")


def write_memory(world_dir: Path, character: str, memory: str) -> None:
    _atomic_write(_memory_path(world_dir, character), memory)
