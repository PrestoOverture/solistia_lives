"""World call recording and replay at the mocked SDK boundary."""

import asyncio
import hashlib
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from typer.testing import CliRunner

from world_replies import commit_fixture_changes

from story_engine.agents import world as agents
from story_engine.cli import app
from story_engine.config import load_configs
from story_engine.runs import create_run
from story_engine.trace import TraceWriter
from story_engine.world.io import append_event, load_state
from story_engine.world.models import Event

ROOT = Path(__file__).resolve().parents[2]


def hashes(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in path.rglob("*") if p.is_file()}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    for name in ("config", "prompts"):
        shutil.copytree(ROOT / name, tmp_path / name)
    world = tmp_path / "worlds/test"
    shutil.copytree(ROOT / "tests/fixtures/worlds/agnea_throne", world)
    monkeypatch.chdir(tmp_path)
    models, settings = load_configs()
    run = create_run(["agnea", "throne"], "cropdale", "Festival", "simulation", None,
                     models, world_id="test", day=1)
    state = load_state(world)
    return world, run, state, models.world, settings.agent_max_turns


def fake(monkeypatch, replies):
    replies = iter(replies)
    clients = []

    class Client:
        def __init__(self, *, options):
            self.options, self.requests, self.closed = options, [], False
            clients.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self.closed = True

        async def query(self, request):
            self.requests.append(request)

        async def receive_response(self):
            yield ResultMessage("success", 1, 1, False, 1, "fake",
                                structured_output=next(replies),
                                total_cost_usd=.01 * len(self.requests))

    monkeypatch.setattr(agents, "ClaudeSDKClient", Client)
    return clients


def adjudicate_reply():
    return dict(call="adjudicate", encounters=[])


def offscreen_reply(state):
    return dict(call="offscreen", events=[dict(place="cropdale", content="The bell rings.",
        ops=[dict(op="place", slug="cropdale", add_details=["A bell tower"])])],
        situation_notes={s.id: "Unchanged." for s in state.situations})


def add_event(world, *, day=1, part="morning"):
    return append_event(world, Event(id=0, day=day, part=part, place="cropdale",
                                    actor="world", type="world", content="The bell rings.",
                                    perceived_by=[]))


def record(setup, call, monkeypatch):
    world, run, state, role, max_turns = setup
    cls = agents.WorldAgent if call == "adjudicate" else agents.OffscreenAgent
    reply = adjudicate_reply() if call == "adjudicate" else offscreen_reply(state)
    clients = fake(monkeypatch, [reply, reply])
    choices = {"agnea": {"aim": "Wait", "where": "cropdale"}}
    # The log has a previous day, and two different parts of the recorded day.
    previous = add_event(world, day=0)
    first = add_event(world)

    async def exercise():
        async with cls(Path.cwd(), run, world, role, max_turns, TraceWriter(run)) as agent:
            async def invoke(events):
                if call == "adjudicate":
                    await agent.adjudicate(state, choices, events)
                else:
                    await agent.offscreen(state, {s.id for s in state.situations})
            await invoke([previous, first])
            state.clock.part = "afternoon"
            second = add_event(world, part="afternoon")
            await invoke([previous, first, second])

    asyncio.run(exercise())
    # These must never reach the replay request.
    add_event(world, part="night")
    add_event(world, day=2)
    return clients, choices


@pytest.mark.parametrize("call", ["adjudicate", "offscreen"])
def test_traces_always_record_full_input(setup, monkeypatch, call):
    world, run, state, _, _ = setup
    clients, choices = record(setup, call, monkeypatch)
    requests = [json.loads(request) for request in clients[0].requests]
    assert "state_changes" in requests[1] and "state" not in requests[1]
    rows = [row for line in (run / "trace.jsonl").read_text().splitlines()
            if (row := json.loads(line))["type"] == "call_input"]
    assert len(rows) == 2
    for index, row in enumerate(rows):
        assert row["call"] == call
        assert row["agent"] == ("world" if call == "adjudicate" else "world_offscreen")
        assert (row["turn"], row["day"], row["max_event_id"]) == (index + 1, 1, index + 2)
        expected = state.model_dump(exclude={} if call == "adjudicate" else {
            "characters": True, "situations": {"__all__": {"touches"}}})
        expected["clock"]["part"] = "morning" if index == 0 else "afternoon"
        assert row["state"] == expected
        if call == "adjudicate":
            assert row["choices"] == choices
        else:
            assert row["validation_state"]["characters"] == state.model_dump()["characters"]


@pytest.mark.parametrize("call", ["adjudicate", "offscreen"])
@pytest.mark.parametrize("selected_turn,repeat,count", [(None, 1, 2), (2, 2, 2), (1, 1, 1)])
def test_replay_full_request_filters_repeats_and_preserves_world(setup, monkeypatch, call,
                                                               selected_turn, repeat, count):
    world, source, state, _, _ = setup
    originals, choices = record(setup, call, monkeypatch)
    # A later world state must never replace the recorded call state.
    state.characters["agnea"].goals = ["A later goal"]
    commit_fixture_changes(world, state)
    before, source_before = hashes(world), hashes(source)
    reply = adjudicate_reply() if call == "adjudicate" else offscreen_reply(state)
    clients = fake(monkeypatch, [reply] * count)
    args = ["eval", "replay", source.name, "--call", call, "--repeat", str(repeat)]
    if selected_turn is not None:
        args += ["--turn", str(selected_turn)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    report = json.loads((run / "replay.json").read_text())
    assert report["source_run_id"] == source.name
    assert len(report["results"]) == len(clients) == count
    assert hashes(world) == before
    assert hashes(source) == source_before
    assert hashes(run / "world") == before  # no save_state or append_event, even in the copy
    meta = json.loads((run / "meta.json").read_text())
    assert (meta["mode"], meta["status"], meta["world_id"]) == ("replay", "passed", "test")
    recorded = {row["turn"]: row for line in (source / "trace.jsonl").read_text().splitlines()
                if (row := json.loads(line))["type"] == "call_input"}
    for client, row in zip(clients, report["results"]):
        assert client.closed and len(client.requests) == 1
        assert client.options.system_prompt == originals[0].options.system_prompt
        assert client.options.setting_sources == []
        request = json.loads(client.requests[0])
        turn = row["turn"]
        assert turn == selected_turn if selected_turn is not None else turn in (1, 2)
        assert request["state"] == recorded[turn]["state"]
        assert "state_changes" not in request
        assert row["cost_usd"] == .01 and row["error"] is None
        if call == "adjudicate":
            assert [event["id"] for event in request["events"]] == ([2] if turn == 1 else [2, 3])
            assert request["choices"] == choices
            assert row["ops"] == []
            assert row["encounters"] == reply["encounters"]
        else:
            assert "events" not in request
            assert "characters" not in request["state"]
            assert all("touches" not in item for item in request["state"]["situations"])
            assert [event["content"] for event in row["events"]] == ["The bell rings."]
            assert row["events"][0]["ops"] == [dict(op="place", slug="cropdale", add_details=["A bell tower"])]
    if repeat == 2:
        assert [row["repeat"] for row in report["results"]] == [1, 2]


def test_replay_offscreen_request_preserves_isolation(setup, monkeypatch):
    world, source, state, _, _ = setup
    # Keep the public projection neutral so private data can only leak from
    # characters, touches, or the event log.
    for place in state.places:
        place.details = []
    for situation in state.situations:
        situation.next = "The clock advances."
    append_event(world, Event(
        id=0, day=1, part="morning", place="cropdale", actor="agnea",
        type="plan", content="agnea plans to search the workshop.",
        intent="Find the textiles before throne arrives.", perceived_by=["agnea"]))
    originals, _ = record(setup, "offscreen", monkeypatch)
    clients = fake(monkeypatch, [offscreen_reply(state)])
    result = CliRunner().invoke(app, [
        "eval", "replay", source.name, "--call", "offscreen", "--turn", "1"])
    assert result.exit_code == 0, result.output
    assert len(clients) == 1 and len(clients[0].requests) == 1
    request = clients[0].requests[0]
    keys = set()

    def collect_keys(pairs):
        keys.update(key for key, _ in pairs)
        return dict(pairs)

    payload = json.loads(request, object_pairs_hook=collect_keys)
    assert not keys & {"events", "characters", "intent"}
    assert all(slug not in request.lower() for slug in state.characters)
    assert payload == json.loads(originals[0].requests[0])
    run = Path(result.output.strip())
    recorded = [json.loads(line) for line in (source / "trace.jsonl").read_text().splitlines()
                if json.loads(line)["type"] == "call_input"][0]
    replayed = [json.loads(line) for line in (run / "trace.jsonl").read_text().splitlines()
                if json.loads(line)["type"] == "call_input"][0]
    assert replayed["max_event_id"] == recorded["max_event_id"] == 3


@pytest.mark.parametrize("call", ["adjudicate", "offscreen"])
@pytest.mark.parametrize("recover", [True, False])
def test_replay_reuses_validation_and_retries(setup, monkeypatch, call, recover):
    _, source, state, _, _ = setup
    record(setup, call, monkeypatch)
    good = adjudicate_reply() if call == "adjudicate" else offscreen_reply(state)
    invalid = (dict(call="adjudicate", ops=[dict(op="clock", day=2, part="night")]) if call == "adjudicate"
               else dict(call="offscreen", events=[dict(
                   actor="agnea", place="cropdale", type="world", content="Waits.")]))
    clients = fake(monkeypatch, [invalid, good if recover else invalid])
    result = CliRunner().invoke(app, ["eval", "replay", source.name, "--call", call, "--turn", "1"])
    passed = recover or call == 'adjudicate'  # a repeated op rejection drops the event
    assert result.exit_code == (0 if passed else 1), result.output
    run = next(p.parent for p in Path("runs").glob("*/replay.json"))
    row = json.loads((run / "replay.json").read_text())["results"][0]
    assert len(clients) == 1 and len(clients[0].requests) == 2
    assert clients[0].requests[1].startswith("World validation failed:")
    assert row["cost_usd"] == .02
    assert (row["error"] is None) == passed
    assert json.loads((run / "meta.json").read_text())["status"] == ("passed" if passed else "failed")
    if call == 'adjudicate' and not recover:
        assert row['ops'] == []
        drops = [r for line in (run / 'trace.jsonl').read_text().splitlines()
                 if (r := json.loads(line))['type'] == 'event_dropped']
        assert len(drops) == 1 and drops[0]['event']['ops'] == invalid['ops']


def test_run_without_call_input_has_clear_error(setup, monkeypatch):
    _, source, _, _, _ = setup
    clients = fake(monkeypatch, [])
    result = CliRunner().invoke(app, ["eval", "replay", source.name, "--call", "adjudicate"])
    assert result.exit_code == 1
    assert "no call_input" in result.output
    assert "requires a run recorded with call_input tracing" in result.output
    assert not clients
    assert len(list(Path("runs").iterdir())) == 1


def test_unmatched_turn_has_clear_error(setup, monkeypatch):
    _, source, _, _, _ = setup
    record(setup, "adjudicate", monkeypatch)
    clients = fake(monkeypatch, [])
    result = CliRunner().invoke(app, ["eval", "replay", source.name, "--call", "adjudicate", "--turn", "99"])
    assert result.exit_code == 1
    assert "no call_input for adjudicate at turn 99" in result.output
    assert not clients


def test_replay_help():
    result = CliRunner().invoke(app, ["eval", "replay", "--help"])
    assert result.exit_code == 0
    for option in ("--call", "--turn", "--repeat", "--models"):
        assert option in result.output
