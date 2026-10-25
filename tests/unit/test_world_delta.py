from world_replies import day_start_reply, commit_fixture_changes
"""State deltas exercised at the SDK request boundary, without model calls."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from story_engine.agents import world as world_agent
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state
from story_engine.world.models import Person, Place

ROOT = Path(__file__).resolve().parents[2]
CALLS = ["day_start", "adjudicate", "scene_round", "offscreen"]


@pytest.fixture
def session_setup(tmp_path, monkeypatch):
    world, run = tmp_path / "world", tmp_path / "run"
    shutil.copytree(ROOT / "tests/fixtures/worlds/agnea_throne", world)
    run.mkdir()
    state = load_state(world)
    state.people["Tam"] = Person(where="cropdale", wants=["Sell berries"], commitments=[])
    state.people["Gus"] = Person(where="cropdale", wants=["Rest"], commitments=[])
    state.places.append(Place(slug="unused_place", details=[]))
    commit_fixture_changes(world, state)
    new_situation = state.situations[0].model_dump() | {"id": "delta-new"}
    requests, clients = [], []

    class FakeClient:
        def __init__(self, *, options):
            self.requests = []
            self.fail_next = False
            self.offscreen_places = []
            clients.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            requests.append(request)
            self.requests.append(request)
            if request.startswith("{"):
                self.call = json.loads(request)["call"]

        async def receive_response(self):
            reply = {
                "day_start": day_start_reply(situations=[dict(new_situation, id="delta-new" if len(requests) == 1 else f"delta-new-{len(requests)}")]),
                "adjudicate": dict(call="adjudicate"),
                "scene_round": dict(call="scene_round"),
                "offscreen": dict(call="offscreen", events=[dict(place="cropdale", ops=[dict(op="place", slug=p["slug"], add_details=p["details"])
                                                                             for p in self.offscreen_places])]),
            }[self.call]
            if self.fail_next:
                self.fail_next = False
                reply = {"call": self.call} if self.call == "day_start" else {"call": "invalid"}
            yield ResultMessage("success", 1, 1, False, 1, "fake", structured_output=reply)

    monkeypatch.setattr(world_agent, "ClaudeSDKClient", FakeClient)
    models, settings = load_configs()

    def session(call):
        cls = world_agent.OffscreenAgent if call == "offscreen" else world_agent.WorldAgent
        return cls(ROOT, run, world, models.world, settings.agent_max_turns, TraceWriter(run))

    return state, session, requests, clients


async def invoke(agent, call, state):
    if call == "day_start":
        return await agent.day_start(state, [])
    if call == "adjudicate":
        return await agent.adjudicate(state, {}, [])
    if call == "scene_round":
        return await agent.round(state, [], place="cropdale", main_present=["agnea"],
                                 minor_present=[], last_winner=None, scene="1", round_number=1)
    return await agent.offscreen(state, set())


def projection(state, call):
    if call == "offscreen":
        return state.model_dump(exclude={
            "characters": True, "situations": {"__all__": {"touches"}},
        })
    return state.model_dump()


@pytest.mark.parametrize("call", CALLS)
def test_full_state_once_then_empty_delta_and_new_session(session_setup, call):
    state, session, requests, clients = session_setup

    async def exercise():
        async with session(call) as agent:
            await invoke(agent, call, state)
            await invoke(agent, call, state)
        async with session(call) as agent:
            await invoke(agent, call, state)

    asyncio.run(exercise())
    first, second, fresh = map(json.loads, requests)
    assert first["state"] == fresh["state"] == projection(state, call)
    assert "state_changes" not in first and "state_changes" not in fresh
    assert "state" not in second
    assert second["state_changes"] == {}
    assert [len(client.requests) for client in clients] == [2, 1]


@pytest.mark.parametrize("call", CALLS)
def test_only_changed_person_sent_in_delta(session_setup, call):
    state, session, requests, _clients = session_setup

    async def exercise():
        async with session(call) as agent:
            await invoke(agent, call, state)
            # In-place mutation also verifies the previous snapshot is independent.
            state.people["Tam"].wants.append("Find a buyer")
            await invoke(agent, call, state)

    asyncio.run(exercise())
    second = json.loads(requests[1])
    assert "state" not in second
    assert second["state_changes"] == {"people": {"Tam": state.people["Tam"].model_dump()}}


@pytest.mark.parametrize("call", CALLS)
def test_removed_person_listed_in_delta(session_setup, call):
    state, session, requests, _clients = session_setup

    async def exercise():
        async with session(call) as agent:
            await invoke(agent, call, state)
            del state.people["Tam"]
            await invoke(agent, call, state)

    asyncio.run(exercise())
    assert json.loads(requests[1])["state_changes"] == {"removed": {"people": ["Tam"]}}


@pytest.mark.parametrize("call", ["adjudicate", "offscreen"])
def test_deltas_add_update_and_remove_entries_and_clock(session_setup, call):
    state, session, requests, _clients = session_setup
    before = state.model_copy(deep=True)

    async def exercise():
        async with session(call) as agent:
            await invoke(agent, call, state)
            state.clock.part = "night"
            state.people["Tam"].spot = "stall"
            del state.people["Gus"]
            state.people["Mabel"] = Person(where="cropdale", wants=["Visit"], commitments=[])
            state.places[0].details.append("a new stall")
            state.places.pop()
            state.places.append(Place(slug="new_place", details=[]))
            state.situations[0].status = "resolved"
            state.situations.pop(1)
            state.situations.append(state.situations[0].model_copy(update={"id": "new-situation"}))
            state.characters["agnea"].spot = "tavern"
            if call == "adjudicate":
                del state.characters["throne"]
                state.characters["castti"] = state.characters["agnea"].model_copy(deep=True)
            await invoke(agent, call, state)

    asyncio.run(exercise())
    data = projection(state, call)
    expected = {
        "clock": data["clock"],
        "people": {name: data["people"][name] for name in ("Tam", "Mabel")},
        "places": [data["places"][0], data["places"][-1]],
        "situations": [data["situations"][0], data["situations"][-1]],
        "removed": {"people": ["Gus"], "places": [before.places[-1].slug],
                    "situations": [before.situations[1].id]},
    }
    if call == "adjudicate":
        expected["characters"] = data["characters"]
        expected["removed"]["characters"] = ["throne"]
    second = json.loads(requests[1])
    assert "state" not in second
    assert second["state_changes"] == expected


def test_offscreen_deltas_exclude_main_character_and_touches_changes(session_setup):
    state, session, requests, _clients = session_setup

    async def exercise():
        async with session("offscreen") as agent:
            await invoke(agent, "offscreen", state)
            state.characters["agnea"].goals.append("Private new goal")
            state.situations[0].touches = ["throne"]
            await invoke(agent, "offscreen", state)
            state.situations[0].status = "resolved"
            await invoke(agent, "offscreen", state)
            state.characters["throne"].spot = "somewhere else"
            state.situations.pop(0)
            await invoke(agent, "offscreen", state)
            assert "characters" not in agent.last_state
            assert all("touches" not in item for item in agent.last_state["situations"])

    asyncio.run(exercise())
    payloads = list(map(json.loads, requests))
    assert payloads[1]["state_changes"] == {}
    assert payloads[2]["state_changes"] == {
        "situations": [payloads[0]["state"]["situations"][0] | {"status": "resolved"}],
    }
    assert payloads[3]["state_changes"] == {
        "removed": {"situations": [payloads[0]["state"]["situations"][0]["id"]]},
    }
    for payload in payloads:
        assert set(payload) == {"call", "reply", "state" if "state" in payload else "state_changes"}
        assert "characters" not in json.dumps(payload)
        assert "touches" not in json.dumps(payload)
        assert "Private new goal" not in json.dumps(payload)


def test_world_calls_share_last_sent_state_not_last_reply(session_setup):
    state, session, requests, _clients = session_setup

    async def exercise():
        async with session("day_start") as agent:
            updated = await invoke(agent, "day_start", state)
            await invoke(agent, "adjudicate", updated)
            await invoke(agent, "scene_round", updated)

    asyncio.run(exercise())
    first, second, third = map(json.loads, requests)
    assert first["state"] == state.model_dump()
    assert second["state_changes"] == {
        "situations": [state.situations[0].model_dump() | {"id": "delta-new"}],
    }
    assert third["state_changes"] == {}
    assert "state" not in second and "state" not in third


@pytest.mark.parametrize("call", CALLS)
def test_retry_feedback_unchanged_and_next_call_diffs_last_input(session_setup, call):
    state, session, requests, _clients = session_setup

    async def exercise():
        async with session(call) as agent:
            agent.client.fail_next = True
            await invoke(agent, call, state)
            await invoke(agent, call, state)

    asyncio.run(exercise())
    assert "state" in json.loads(requests[0])
    assert requests[1].startswith("World validation failed: ")
    assert requests[1].endswith("\nReturn corrected JSON.")
    assert json.loads(requests[2])["state_changes"] == {}
    assert "state" not in json.loads(requests[2])


@pytest.mark.parametrize("update_place", [False, True])
def test_offscreen_reply_keeps_omitted_places_and_merges_by_slug(session_setup, update_place):
    state, session, _requests, _clients = session_setup
    original = state.model_copy(deep=True)
    changed = state.places[0].model_dump() | {"details": ["updated stall"]}
    added = {"slug": "new_place", "details": ["new room"]}

    async def exercise():
        async with session("offscreen") as agent:
            if update_place:
                agent.client.offscreen_places = [changed, added]
            return await invoke(agent, "offscreen", state)

    _events, updated, _notes = asyncio.run(exercise())
    by_slug = {place.slug: place.model_dump() for place in updated.places}
    expected = {place.slug: place.model_dump() for place in original.places}
    if update_place:
        expected.update({changed["slug"]: dict(changed, details=original.places[0].details + changed["details"]), added["slug"]: added})
    assert by_slug == expected
    assert len(updated.places) == len(expected)
    assert state == original


@pytest.mark.parametrize("call", ["adjudicate", "offscreen"])
def test_reordered_lists_are_not_state_changes(session_setup, call):
    state, session, requests, _clients = session_setup

    async def exercise():
        async with session(call) as agent:
            await invoke(agent, call, state)
            state.places.reverse()
            state.situations.reverse()
            await invoke(agent, call, state)

    asyncio.run(exercise())
    assert json.loads(requests[1])["state_changes"] == {}
