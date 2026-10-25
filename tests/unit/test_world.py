import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from story_engine.world import (
    Event, WorldInfo, WorldState, append_event, create_world, load_state,
    read_events, read_memory, save_state, write_memory,
)


@pytest.fixture
def state_data():
    return {
        "clock": {"day": 1, "part": "afternoon"},
        "places": [{"slug": "cropdale", "details": ["a pie stall"]}],
        "characters": {
            "agnea": {"where": "cropdale", "goals": ["Help at the festival"],
                      "commitments": [{"what": "Help Papa", "where": "cropdale",
                                       "day": 1, "part": "evening"}]},
            "throne": {"where": "cropdale", "goals": ["Find quiet"], "commitments": []},
        },
        "people": {
            "keeper": {"where": "cropdale", "wants": ["Find the book"], "commitments": []},
        },
        "situations": [{"id": "book", "kind": "trouble", "summary": "A book is missing",
                        "touches": ["agnea"], "people": ["keeper"], "status": "open",
                        "next": "Contest cancelled", "due": {"day": 1, "part": "evening"}}],
    }


def make_world(tmp_path, state_data):
    return create_world(["agnea", "throne"], "cropdale", "Festival",
                        WorldState.model_validate(state_data), worlds_dir=tmp_path / "worlds")


def event(**changes):
    data = dict(id=999, day=1, part="afternoon", place="cropdale", actor="agnea",
                type="speech", content="Hello.", intent="Offer help", perceived_by=["throne"])
    return Event(**(data | changes))


def test_round_trip_and_event_reopening(tmp_path, state_data):
    world = make_world(tmp_path, state_data)
    assert world.parent == tmp_path / "worlds"
    info = WorldInfo.model_validate_json((world / "world.json").read_text())
    assert info.characters == ["agnea", "throne"]
    assert info.location == "cropdale" and info.situation == "Festival" and info.created_at
    assert WorldInfo.model_validate_json(info.model_dump_json()) == info
    state = load_state(world)
    assert state.model_dump(exclude={"characters": {"agnea": {"commitments"}}}) == WorldState.model_validate(state_data).model_dump(exclude={"characters": {"agnea": {"commitments"}}})
    state.clock.part = "night"
    save_state(world, state)
    assert load_state(world) == state
    first = append_event(world, event())
    prefix = (world / "events.jsonl").read_bytes()
    second = append_event(world, event(type="action", content="Waves."))
    assert (world / "events.jsonl").read_bytes().startswith(prefix)
    reopened = Path(str(world))
    third = append_event(reopened, event(actor="world", intent=None, type="world"))
    assert read_events(reopened)[1:] == [first, second, third]
    assert [e.id for e in read_events(world)] == [1, 2, 3, 4]
    write_memory(world, "agnea", "# Today\nHelped at the festival.\n")
    assert read_memory(reopened, "agnea") == "# Today\nHelped at the festival.\n"
    assert (world / "memory" / "agnea.md").is_file()


@pytest.mark.parametrize("invalid", [
    "part", "where", "missing", "extra", "goals", "situation_id",
    "touches_empty", "touches_minor", "status", "commitment_part", "due_part",
    "situation_people_unknown", "person_name_main_character", "person_where_invalid",
])
def test_reject_invalid_state(tmp_path, state_data, invalid):
    world = make_world(tmp_path, state_data)
    original = (world / "state.json").read_bytes()
    match invalid:
        case "part": state_data["clock"]["part"] = "dawn"
        case "where": state_data["characters"]["agnea"]["where"] = "unknown"
        case "missing": del state_data["characters"]["throne"]
        case "extra": state_data["characters"]["other"] = state_data["characters"]["throne"]
        case "goals": state_data["characters"]["agnea"]["goals"] = []
        case "situation_id": state_data["situations"].append(state_data["situations"][0].copy())
        case "touches_empty": state_data["situations"][0]["touches"] = []
        case "touches_minor": state_data["situations"][0]["touches"] = ["agnea", "keeper"]
        case "status": state_data["situations"][0]["status"] = "pending"
        case "commitment_part": state_data["characters"]["agnea"]["commitments"][0]["part"] = "dawn"
        case "due_part": state_data["situations"][0]["due"]["part"] = "dawn"
        case "situation_people_unknown": state_data["situations"][0]["people"] = ["ghost"]
        case "person_name_main_character":
            state_data["people"]["Throné"] = {"where": "cropdale", "wants": ["Something"], "commitments": []}
        case "person_where_invalid": state_data["people"]["keeper"]["where"] = "unknown"
    with pytest.raises(ValueError):
        save_state(world, WorldState.model_validate(state_data))
    assert (world / "state.json").read_bytes() == original
    (world / "genesis.json").write_text(json.dumps(state_data))
    with pytest.raises(ValueError):
        load_state(world)


def test_duplicate_character_json_rejected(tmp_path, state_data):
    world = make_world(tmp_path, state_data)
    raw = json.dumps(state_data)
    character = json.dumps(state_data["characters"]["agnea"])
    raw = raw.replace('"characters": {', '"characters": {"agnea": ' + character + ', ', 1)
    (world / "genesis.json").write_text(raw)
    with pytest.raises(ValueError, match="duplicate JSON key: agnea"):
        load_state(world)
    with pytest.raises(ValidationError):
        WorldInfo(characters=["agnea", "agnea"], location="cropdale", situation="Festival",
                  created_at="now")


def test_mutated_state_is_revalidated(tmp_path, state_data):
    world = make_world(tmp_path, state_data)
    state = load_state(world)
    state.characters["agnea"].goals.clear()
    with pytest.raises(ValueError):
        save_state(world, state)


def test_atomic_state_replacement_failure(tmp_path, state_data, monkeypatch):
    world = make_world(tmp_path, state_data)
    original = (world / "state.json").read_bytes()
    def fail_replace(*args):
        raise OSError("replacement failed")
    monkeypatch.setattr("story_engine.world.io.os.replace", fail_replace)
    with pytest.raises(OSError):
        state = load_state(world)
        state.clock.day += 1
        save_state(world, state)
    assert (world / "state.json").read_bytes() == original
    assert not list(world.glob(".state.json.*"))


def test_event_and_memory_rejections(tmp_path, state_data):
    world = make_world(tmp_path, state_data)
    with pytest.raises(ValidationError):
        event(part="dawn")
    with pytest.raises(ValidationError):
        event(type="thought")
    with pytest.raises(ValueError):
        append_event(world, event(actor="keeper"))
    assert read_events(world) == []
    with pytest.raises(ValueError):
        write_memory(world, "../escape", "no")


@pytest.mark.parametrize('case,values', [
    ('characters', ['missing_town', 'lost_town']),
    ('people_where', ['missing_town', 'lost_town']),
    ('people_names', ['Ghost', 'Stranger', 'keeper']),
    ('touches', ['outsider', 'stranger']),
    ('duplicate_ids', ['book', 'second']),
    ('main_name', ['Throné']),
])
def test_reference_errors_name_values(state_data, case, values):
    if case == 'characters':
        for character, where in zip(state_data['characters'].values(), values):
            character['where'] = where
    elif case == 'people_where':
        state_data['people']['keeper']['where'] = values[0]
        state_data['people']['visitor'] = dict(where=values[1], wants=['Visit'], commitments=[])
    elif case == 'people_names':
        state_data['situations'][0]['people'] = values[:2]
    elif case == 'touches':
        state_data['situations'][0]['touches'] = values
    elif case == 'duplicate_ids':
        second = dict(state_data['situations'][0], id='second')
        state_data['situations'] += [dict(state_data['situations'][0]), second, dict(second)]
    else:
        state_data['people']['Throné'] = dict(where='cropdale', wants=['Visit'], commitments=[])
    with pytest.raises(ValidationError) as caught:
        WorldState.model_validate(state_data)
    message = caught.value.errors(include_input=False)[0]['msg']
    assert all(value in message for value in values)


def test_duplicate_world_characters_names_value():
    with pytest.raises(ValidationError) as caught:
        WorldInfo(characters=['agnea', 'agnea'], location='cropdale', situation='Visit', created_at='now')
    assert 'agnea' in caught.value.errors(include_input=False)[0]['msg']
