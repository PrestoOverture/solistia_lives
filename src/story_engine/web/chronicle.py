"""Read-only situation threads linked solely by artifact fields and ids."""

from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from story_engine.config import load_settings
from story_engine.kb import kb_names
from story_engine.stages import load_catalogs
from story_engine.web.player import display_name, valid_id
from story_engine.world.io import read_events, read_scenes
from story_engine.world.models import Clock, Event, SceneRecord, Situation, WorldInfo, WorldState
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


def scene_entry(world_id: str, scene: SceneRecord, events: list[Event], names: dict, locations: dict,
                theater_url: str | None = None) -> SceneEntry:
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
                      theater_link=f'{theater_url or f"/world/{world_id}/theater"}#{scene.id}')


def chronicle_data(worlds_dir: Path, world_id: str, names: dict, locations: dict,
                   theater_url: str | None = None) -> Chronicle:
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
    explicit = any(e.about is not None for e in events)
    for event in events:
        if event.about in linked and event.scene is not None:
            linked[event.about].add(event.scene)
    parts = load_settings().parts_of_day

    def when(item):
        return item.day, parts.index(item.part)

    def inside(thread, item):
        return when(thread.opened) <= when(item) and (thread.closed is None or when(item) <= when(thread.closed))

    entries = {s.id: scene_entry(world_id, s, events, names, locations, theater_url) for s in scenes}
    used = set()
    for thread in threads.values():
        thread.scenes = [entries[s.id] for s in scenes if s.id in linked[thread.id]
                         or (not explicit and inside(thread, s) and people[thread.id].intersection(s.participants))]
        used.update(s.id for s in thread.scenes)
        thread.off_scene = [e for e in events if e.scene is None and e.type != 'plan'
                            and (e.about == thread.id if explicit else
                                 e.content and e.actor in people[thread.id] and inside(thread, e))]
    off_scene_ids = {e.id for thread in threads.values() for e in thread.off_scene}
    elsewhere = [e for e in events if e.scene is None and e.type != 'plan'
                 and e.content and e.id not in off_scene_ids]
    return Chronicle(world_id=world_id, threads=sorted(threads.values(), key=lambda t: (
        *when(t.opened), t.opened.event_id or 0)),
        unthreaded=[entries[s.id] for s in scenes if s.id not in used], elsewhere=elsewhere)


def thread_timelines(chronicle: Chronicle, scenes: list[SceneRecord], parts: list[str]) -> dict:
    """HTML-only ordering; leave the chronicle's serialized contract untouched.

    Combine facts from the same event so a closing or update linked off-scene
    appears once. A scene occupies the position of its first logged event.
    """
    first_ids = {scene.id: scene.first_event_id for scene in scenes}
    timelines = {}
    for thread in chronicle.threads:
        events = {}

        def entry(item, event_id):
            return events.setdefault(event_id, dict(
                kind='event', day=item.day, part=item.part, event_id=event_id,
                opened=None, event=None, updates=[], change=None, closed=None))

        entry(thread.opened, thread.opened.event_id or 0)['opened'] = thread.opened
        for event in thread.off_scene:
            entry(event, event.id)['event'] = event
        for update in thread.updates:
            entry(update, update.event_id)['updates'].append(update)
        for change in thread.status_history:
            entry(change, change.event_id)['change'] = change
        if thread.closed:
            entry(thread.closed, thread.closed.event_id)['closed'] = thread.closed
        rows = [*events.values(), *(dict(kind='scene', day=scene.day, part=scene.part,
                event_id=first_ids[scene.id], scene=scene) for scene in thread.scenes)]
        timelines[thread.id] = sorted(rows, key=lambda row: (
            row['day'], parts.index(row['part']), row['event_id'], row['kind'] != 'scene'))
    return timelines


def chronicle_page(worlds_dir: Path, world_id: str, player_assets_dir: Path, travelers: dict, locations: dict,
                   theater_url: str | None = None) -> dict:
    """The chronicle template's context; raises ValueError (or OSError, KeyError) for a missing world."""
    directory = worlds_dir / world_id
    if not valid_id(world_id) or directory.is_symlink() or (directory / 'world.json').is_symlink():
        raise ValueError('World not found')
    info = WorldInfo.model_validate_json((directory / 'world.json').read_bytes())
    if info.setting is not None:
        travelers, locations = kb_names(info.setting, info.characters)
    item = chronicle_data(worlds_dir, world_id, travelers, locations, theater_url)

    def field_text(field, value):
        """Format structured values only; never interpret event prose."""
        if isinstance(value, dict):
            if set(value) == {'day', 'part'}:
                return f"Day {value['day']} {value['part']}"
            return ' · '.join(f'{key} → {field_text(key, item)}' for key, item in value.items())
        if isinstance(value, list):
            return ', '.join(field_text(field, item) for item in value) or '—'
        if field in {'people', 'touches', 'opposed_by', 'who', 'person', 'main', 'name', 'heard_from'}:
            return display_name(value, travelers) if value is not None else '—'
        if field in {'place', 'where', 'slug'}:
            return locations.get(value, value)
        return str(value) if value is not None else '—'

    def op_text(op):
        fields = op.model_dump(mode='json', exclude_unset=True, exclude={'op'})
        return op.op + ' · ' + field_text('', fields)

    scenes = read_scenes(directory)
    parts = load_settings().parts_of_day
    catalogs = load_catalogs(directory=info.setting or player_assets_dir)
    spot_names = {(place, spot.id): spot.name or spot.id
                  for place, catalog in catalogs.items() for spot in catalog.spots}
    scene_ids = {scene.id for thread in item.threads for scene in thread.scenes}
    scene_ids.update(scene.id for scene in item.unthreaded)
    return dict(
        chronicle=item, scene_count=len(scene_ids), person=lambda slug: display_name(slug, travelers),
        field_text=field_text, op_text=op_text,
        parts_of_day=parts, timelines=thread_timelines(item, scenes, parts),
        world_title=', '.join(display_name(name, travelers) for name in info.characters)
                    + ' · ' + locations.get(info.location, info.location),
        day_count=max([1, *(scene.day for scene in scenes),
                       *(event.day for event in read_events(directory))]), spot_names=spot_names)


def register_chronicle_routes(app, templates, worlds_dir: Path, player_assets_dir: Path,
                              travelers: dict, locations: dict):
    def data(world_id):
        directory = worlds_dir / world_id
        try:
            if not valid_id(world_id) or directory.is_symlink() or (directory / 'world.json').is_symlink():
                raise ValueError('World not found')
            info = WorldInfo.model_validate_json((directory / 'world.json').read_bytes())
            names, places = (kb_names(info.setting, info.characters) if info.setting is not None
                             else (travelers, locations))
            return chronicle_data(worlds_dir, world_id, names, places)
        except (OSError, ValueError, KeyError):
            raise HTTPException(status_code=404, detail='World not found') from None

    @app.get('/world/{world_id}/chronicle.json')
    def chronicle_json(world_id: str):
        return data(world_id)

    @app.get('/world/{world_id}/chronicle', response_class=HTMLResponse)
    def chronicle(request: Request, world_id: str):
        try:
            context = chronicle_page(worlds_dir, world_id, player_assets_dir, travelers, locations)
        except (OSError, ValueError, KeyError):
            raise HTTPException(status_code=404, detail='World not found') from None
        return templates.TemplateResponse(request=request, name='chronicle.html', context=context)
