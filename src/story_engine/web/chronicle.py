"""Read-only situation threads linked solely by artifact fields and ids."""

from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from story_engine.config import load_settings
from story_engine.web.player import display_name, valid_id
from story_engine.world.io import read_events, read_scenes
from story_engine.world.models import Clock, Event, SceneRecord, Situation, WorldState
from story_engine.world.ops import Open, SituationOp


class Opening(Clock):
    event_id: int | None = None
    at_start: bool = False


class Update(Clock):
    event_id: int
    scene: str | None
    changed_fields: dict


class Closing(Clock):
    event_id: int
    scene: str | None
    round: int | None
    content: str
    status: str
    by_clock: bool


class RoundEntry(BaseModel):
    round: int
    moves: list[Event]
    world: list[Event]


class SceneEntry(BaseModel):
    id: str
    day: int
    part: str
    place: str
    place_name: str
    spot: str | None
    participants: list[str]
    rounds: list[RoundEntry]
    end: str
    theater_link: str


class Thread(Situation):
    opened: Opening
    updates: list[Update] = Field(default_factory=list)
    closed: Closing | None = None
    status_history: list[Closing] = Field(default_factory=list)
    scenes: list[SceneEntry] = Field(default_factory=list)
    off_scene: list[Event] = Field(default_factory=list)


class Chronicle(BaseModel):
    world_id: str
    threads: list[Thread]
    unthreaded: list[SceneEntry]
    elsewhere: list[Event]


def scene_entry(world_id: str, scene: SceneRecord, events: list[Event], names: dict, locations: dict) -> SceneEntry:
    rows = [e for e in events if e.scene == scene.id and e.type != 'plan']
    rounds = []
    numbers = sorted(set(range(1, scene.rounds + 1)) | {e.round for e in rows if e.round is not None})
    for number in numbers:
        moves = [e for e in rows if e.round == number and e.type in {'action', 'speech'}]
        outcomes = [e for e in rows if e.actor == 'world' and e.round == number]
        rounds.append(RoundEntry(round=number, moves=moves, world=outcomes))
    return SceneEntry(**scene.model_dump(exclude={'rounds', 'participants', 'first_event_id', 'last_event_id'}),
                      place_name=locations.get(scene.place, scene.place),
                      participants=[display_name(p, names) for p in scene.participants], rounds=rounds,
                      theater_link=f'/world/{world_id}/theater#{scene.id}')


def chronicle_data(worlds_dir: Path, world_id: str, names: dict, locations: dict) -> Chronicle:
    directory = worlds_dir / world_id
    if (not valid_id(world_id) or directory.is_symlink()
            or directory.resolve().parent != worlds_dir.resolve()
            or any((directory / name).is_symlink() for name in
                   ('genesis.json', 'events.jsonl', 'scenes.jsonl'))):
        raise ValueError('World not found')
    genesis = WorldState.model_validate_json((directory / 'genesis.json').read_bytes())
    events, scenes = read_events(directory), read_scenes(directory)
    threads = {s.id: Thread(**s.model_dump(), opened=Opening(day=1, part='morning', at_start=True))
               for s in genesis.situations}
    people = {s.id: set(s.people) for s in genesis.situations}
    linked = {s.id: set() for s in genesis.situations}
    for event in events:
        for op in event.ops:
            if isinstance(op, Open):
                s = op.situation
                threads[s.id] = Thread(**s.model_dump(), opened=Opening(
                    day=event.day, part=event.part, event_id=event.id))
                people[s.id], linked[s.id] = set(s.people), set()
            elif isinstance(op, SituationOp):
                thread = threads[op.id]
                changes = op.model_dump(exclude={'op', 'id'}, exclude_unset=True)
                thread.updates.append(Update(event_id=event.id, day=event.day, part=event.part,
                                             scene=event.scene, changed_fields=changes))
                if op.status is not None and op.status != thread.status:
                    thread.status_history.append(Closing(
                        event_id=event.id, day=event.day, part=event.part,
                        scene=event.scene, round=event.round, content=event.content,
                        status=op.status, by_clock=event.op_only))
                for field in changes:
                    setattr(thread, field, getattr(op, field))
                people[op.id].update(thread.people)
                if event.scene is not None:
                    linked[op.id].add(event.scene)
                if op.status in {'resolved', 'dropped'}:
                    thread.closed = Closing(event_id=event.id, day=event.day, part=event.part,
                                            scene=event.scene, round=event.round, content=event.content,
                                            status=op.status, by_clock=event.op_only)
    parts = load_settings().parts_of_day

    def when(item):
        return item.day, parts.index(item.part)

    def inside(thread, item):
        return when(thread.opened) <= when(item) and (thread.closed is None or when(item) <= when(thread.closed))

    entries = {s.id: scene_entry(world_id, s, events, names, locations) for s in scenes}
    used = set()
    for thread in threads.values():
        thread.scenes = [entries[s.id] for s in scenes if s.id in linked[thread.id]
                         or (inside(thread, s) and people[thread.id].intersection(s.participants))]
        used.update(s.id for s in thread.scenes)
        thread.off_scene = [e for e in events if e.scene is None and e.type != 'plan' and e.content
                            and e.actor in people[thread.id] and inside(thread, e)]
    off_scene_ids = {e.id for thread in threads.values() for e in thread.off_scene}
    elsewhere = [e for e in events if e.scene is None and e.type != 'plan'
                 and e.content and e.id not in off_scene_ids]
    return Chronicle(world_id=world_id, threads=sorted(threads.values(), key=lambda t: (
        *when(t.opened), t.opened.event_id or 0)),
        unthreaded=[entries[s.id] for s in scenes if s.id not in used], elsewhere=elsewhere)


def register_chronicle_routes(app, templates, worlds_dir: Path, travelers: dict, locations: dict):
    def field_text(field, value):
        """Format structured values only; never interpret event prose."""
        if isinstance(value, dict):
            if set(value) == {'day', 'part'}:
                return f"Day {value['day']} {value['part']}"
            return ' · '.join(f'{key} → {field_text(key, item)}' for key, item in value.items())
        if isinstance(value, list):
            return ', '.join(field_text(field, item) for item in value) or '—'
        if field in {'people', 'touches', 'who', 'person', 'main', 'name', 'heard_from'}:
            return display_name(value, travelers) if value is not None else '—'
        if field in {'place', 'where', 'slug'}:
            return locations.get(value, value)
        return str(value) if value is not None else '—'

    def op_text(op):
        fields = op.model_dump(mode='json', exclude_unset=True, exclude={'op'})
        return op.op + ' · ' + field_text('', fields)

    def data(world_id):
        try:
            return chronicle_data(worlds_dir, world_id, travelers, locations)
        except (OSError, ValueError, KeyError):
            raise HTTPException(status_code=404, detail='World not found') from None

    @app.get('/world/{world_id}/chronicle.json')
    def chronicle_json(world_id: str):
        return data(world_id)

    @app.get('/world/{world_id}/chronicle', response_class=HTMLResponse)
    def chronicle(request: Request, world_id: str):
        item = data(world_id)
        scene_ids = {scene.id for thread in item.threads for scene in thread.scenes}
        scene_ids.update(scene.id for scene in item.unthreaded)
        return templates.TemplateResponse(request=request, name='chronicle.html', context=dict(
            chronicle=item, scene_count=len(scene_ids), field_text=field_text, op_text=op_text,
            parts_of_day=load_settings().parts_of_day))
