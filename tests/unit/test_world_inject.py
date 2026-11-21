import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.world.io import end_world, load_state, read_events
from test_day_start import fake_sdk
from world_replies import commit_fixture_changes

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    directory = Path("worlds/test")
    shutil.copytree(ROOT / "tests/fixtures/worlds/agnea_throne", directory)
    return directory


@pytest.mark.parametrize("day", [1, 2])
def test_injected_news_reaches_only_recipient_at_first_plan(world, monkeypatch, day):
    for name in ("config", "prompts", "cards", "kb"):
        Path(name).symlink_to(ROOT / name, target_is_directory=True)
    state = load_state(world)
    state.situations[0].heard = "The weaver has lost a bolt of silk."
    state.situations[1].heard = "The baker is looking for fresh berries."
    (world / "genesis.json").write_text(state.model_dump_json())
    recipient = "throne"
    if day == 2:
        state.clock.day = 2
        state.characters[recipient].where = "cropdale"
        commit_fixture_changes(world, state)
    before = read_events(world)
    if day == 1:
        assert before == []
    else:
        # The clock and move come from legacy rows with no author field.
        assert all("by" not in json.loads(line) for line in (world / "events.jsonl").read_text().splitlines())
    news = "  The ferryman hid a spare oar under the bridge.  "
    runner = CliRunner()
    result = runner.invoke(app, ["world", "inject", world.name, "--to", recipient, news])
    assert result.exit_code == 0, result.output
    *unchanged, note = read_events(world)
    assert unchanged == before
    assert (note.actor, note.type, note.by, note.content) == ("world", "world", "author", news)
    assert (note.day, note.part, note.place) == (day, state.clock.part, state.characters[recipient].where)
    assert note.scene is None and note.about is None and note.ops == []
    assert note.perceived_by == [recipient] and "by" not in note.agent_view()
    assert load_state(world) == state

    def respond(client, request):
        call = request["call"]
        if call == "day_start":
            return dict(call=call, ops=[]) if "state" in request else dict(call=call, goals=["Rest"])
        if call == "part_of_day":
            return dict(call="plan", kind="go", where=client.calls[0]["place"], spot=None,
                        aim="Stay here.", intent="Rest")
        if call == "scene_move":
            return dict(call="action", move="wait", urge=0, action="", say="", intent="Rest")
        if call in {"adjudicate", "scene_round"}:
            return dict(call=call)
        if call == "offscreen":
            return dict(call=call, settle={sid: "dropped" for sid in request.get("due_now", [])},
                        situation_notes={s.id: "Unchanged." for s in load_state(world).situations if s.status == "open"})
        assert call == "end_of_day"
        return dict(call=call, summary="Rested.")

    clients = fake_sdk(monkeypatch, respond)
    result = runner.invoke(app, ["world", "run", world.name, "--stop-after", "day"])
    assert result.exit_code == 0, result.output
    events = read_events(world)
    assert [e for e in events if e.content == news] == [note]
    heard = [s for s in state.situations if day == 1 and s.heard]
    for situation in heard:
        fact, = [e for e in events if e.content == situation.heard]
        assert fact.about == situation.id and fact.perceived_by == situation.touches
        assert fact.id < next(e.id for e in events if e.type == "plan")
    for slug, character in state.characters.items():
        client, = [c for c in clients if c.calls[0].get("goals") == character.goals]
        plan = next(request for request in client.calls if request["call"] == "part_of_day")
        contents = [e["content"] for e in plan["perceived"]]
        # The note reaches the recipient once, in its first request of the day (goal revision or first plan).
        first = next(request for request in client.calls if "perceived" in request)
        assert [e["content"] for e in first["perceived"]].count(news) == int(slug == recipient)
        assert sum(json.dumps(r).count(json.dumps(news)) for r in client.calls) == int(slug == recipient)
        assert all((s.heard in contents) == (slug in s.touches) for s in heard)
        if slug != recipient:
            assert news not in json.dumps(client.calls)
    for client in clients:
        requests = json.dumps(client.calls)
        assert '"by"' not in requests and '"author"' not in requests


@pytest.mark.parametrize("recipient,news,ended,error", [
    ("unknown", "News", False, "Unknown main character"),
    ("throne", "", False, "non-empty"),
    ("throne", "  ", False, "non-empty"),
    ("throne", "x" * 281, False, "at most 280"),
    ("throne", "News", True, "World ended on day"),
])
def test_inject_refuses_without_appending(world, recipient, news, ended, error):
    if ended:
        end_world(world, 1, "settled")
    result = CliRunner().invoke(app, ["world", "inject", world.name, "--to", recipient, news])
    assert result.exit_code == 1 and error in result.output
    assert read_events(world) == []
