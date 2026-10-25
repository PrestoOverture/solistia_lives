"""Path-based storage for worlds; no agent or model calls."""

import json
import os
import secrets
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .models import Event, SceneRecord, WorldInfo, WorldState
from .ops import reduce_ops
from .permissions import Authority


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
    for name, member in {**state.characters, **state.people}.items():
        for index, commitment in enumerate(member.commitments):
            commitment.id = f'genesis:{name}:{index}'
            commitment.scene = None
    _atomic_write(world_dir / "genesis.json", state.model_dump_json(indent=2))
    _atomic_write(world_dir / "state.json", state.model_dump_json(indent=2))
    (world_dir / "events.jsonl").touch()
    (world_dir / "scenes.jsonl").touch()
    return world_dir


def load_state(world_dir: Path) -> WorldState:
    info = WorldInfo.model_validate(_read_json(world_dir / "world.json"))
    genesis = world_dir / "genesis.json"
    if not genesis.exists():
        return _validate_state(info, WorldState.model_validate(_read_json(world_dir / "state.json")))
    state = _validate_state(info, WorldState.model_validate(_read_json(genesis)))
    for event in read_events(world_dir):
        state = reduce_ops(state, event.ops, event_id=event.id, scene=event.scene)
    return _validate_state(info, state)


def validate_state(world_dir: Path, state: WorldState) -> WorldState:
    """Validate a proposed state against the persistent world without writing it."""
    info = WorldInfo.model_validate(_read_json(world_dir / "world.json"))
    return _validate_state(info, state)


def require_genesis(world_dir: Path) -> None:
    if not (world_dir / "genesis.json").exists():
        raise ValueError("Worlds without genesis.json are read-only; create a new world to run")


def commit_state(world_dir: Path, state: WorldState, *, scene: str | None = None,
                 round: int | None = None) -> WorldState:
    """Legacy reply adapter; all durable changes still pass through commit_event."""
    from .adapter import state_ops
    require_genesis(world_dir)
    state = validate_state(world_dir, state)
    before = load_state(world_dir)
    ops = state_ops(before, state)
    if ops:
        commit_event(world_dir, Event(
            id=0, **before.clock.model_dump(), place=before.places[0].slug, actor='world',
            type='state_change', content='', perceived_by=[], scene=scene, round=round, ops=ops), authority=None)
    return load_state(world_dir)


def save_state(world_dir: Path, state: WorldState) -> None:
    """Compatibility entry point for callers outside the day loop, also event sourced."""
    commit_state(world_dir, state)


def read_events(world_dir: Path) -> list[Event]:
    events = []
    with (world_dir / "events.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            event = Event.model_validate_json(line)
            if events and event.id <= events[-1].id:
                raise ValueError("event ids must be strictly increasing")
            events.append(event)
    return events


def commit_event(world_dir: Path, event: Event, *, authority: Authority | None = Authority('code')) -> Event:
    """Assign the next persisted ID and append. World writes are sequential."""
    require_genesis(world_dir)
    events = read_events(world_dir)
    data = event.model_dump()
    data["id"] = events[-1].id + 1 if events else 1
    event = Event.model_validate(data)
    info = WorldInfo.model_validate(_read_json(world_dir / "world.json"))
    if event.intent is not None and event.actor not in info.characters:
        raise ValueError("only main characters may have private intent")
    if (event.resolves is None) != (event.resolution is None):
        raise ValueError('resolves and resolution must be supplied together')
    if event.resolves is not None:
        target = next((old for old in events if old.id == event.resolves), None)
        if (event.scene is None or target is None or target.scene != event.scene
                or target.type not in {'action', 'speech'} or target.round is None):
            raise ValueError('resolves must name an act in the same scene')
        if any(old.resolves == event.resolves and old.resolution != 'pending' for old in events):
            raise ValueError('winning act is already resolved')
    state = load_state(world_dir)
    if authority is not None:
        from .permissions import validate_ops
        state = validate_ops(state, event, authority)
    else:
        state = reduce_ops(state, event.ops, event_id=event.id, scene=event.scene)
    state = validate_state(world_dir, state)
    with (world_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(event.model_dump_json() + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    if event.ops:
        _atomic_write(world_dir / "state.json", state.model_dump_json(indent=2))
    return event


def append_event(world_dir: Path, event: Event) -> Event:
    return commit_event(world_dir, event)


def read_scenes(world_dir: Path) -> list[SceneRecord]:
    path = world_dir / "scenes.jsonl"
    if not path.exists():
        return []
    scenes = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                scenes.append(SceneRecord.model_validate_json(line))
    return scenes


def append_scene(world_dir: Path, scene: SceneRecord) -> SceneRecord:
    """Scenes are appended as-is; the caller assigns the scene id."""
    with (world_dir / "scenes.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(scene.model_dump_json() + "\n")
    return scene


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
