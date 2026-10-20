import copy
import json
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from typer.testing import CliRunner

from story_engine.agents import initializer
from story_engine.cli import app
from story_engine.world.io import load_state

ARGS = ["world", "new", "--characters", "agnea,throne", "--location", "cropdale",
        "--situation", "Agnea has brought Throné to a festival here."]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    source = Path(__file__).resolve().parents[2]
    for name in ("config/models.yaml", "config/settings.yaml", "prompts/initializer_scene_context.md",
                 "prompts/initializer_state.md", "cards/agnea.md", "cards/throne.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((source / name).read_bytes())
    place = tmp_path / "kb/locations/towns/cropdale.md"
    place.parent.mkdir(parents=True)
    place.write_text("# Cropdale")
    monkeypatch.chdir(tmp_path)

    class UnexpectedClient:
        def __init__(self, **kwargs):
            pytest.fail("Unexpected model call")

    monkeypatch.setattr(initializer, "ClaudeSDKClient", UnexpectedClient)
    return tmp_path


@pytest.fixture
def state():
    return {
        "places": [{"slug": "cropdale", "details": ["festival"]}],
        "characters": {slug: {"where": "cropdale", "goals": ["Visit the festival"], "commitments": []}
                       for slug in ("agnea", "throne")},
        "situations": [{"id": "festival", "summary": "A festival", "touches": ["agnea"],
                        "people": [], "status": "open", "next": "The dancing begins",
                        "due": {"day": 1, "part": "evening"}}],
    }


def fake_sdk(monkeypatch, outputs):
    sessions = []

    class FakeClient:
        def __init__(self, *, options):
            self.options = options
            self.index = len(sessions)
            self.queries = []
            sessions.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, prompt):
            self.queries.append(prompt)

        async def receive_response(self):
            output = outputs[len(self.queries) - 1]
            text = "## Location\nCropdale" if self.index == 0 else (
                output if isinstance(output, str) else json.dumps(output)
            )
            yield ResultMessage("success", 1, 1, False, 1, "fake", result=text,
                                usage={"input_tokens": 10, "output_tokens": 20})

    monkeypatch.setattr(initializer, "ClaudeSDKClient", FakeClient)
    return sessions


def test_valid_world(repo, state, monkeypatch):
    state["clock"] = {"day": 99, "part": "night"}
    sessions = fake_sdk(monkeypatch, [state])
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code == 0, result.output
    world = Path(result.output.strip())
    assert {p.name for p in world.iterdir()} == {
        "world.json", "state.json", "events.jsonl", "memory", "scene_context.md"}
    info = json.loads((world / "world.json").read_text())
    run = repo / "runs" / info["init_run_id"]
    assert {"meta.json", "trace.jsonl", "retrieval.jsonl", "scene_context.md"} <= {p.name for p in run.iterdir()}
    assert load_state(world).clock.model_dump() == {"day": 1, "part": "morning"}
    assert (world / "events.jsonl").read_text() == ""
    assert (world / "scene_context.md").read_bytes() == (run / "scene_context.md").read_bytes()
    assert json.loads((run / "meta.json").read_text())["status"] == "passed"
    usage = [json.loads(row) for row in (run / "trace.jsonl").read_text().splitlines()
             if json.loads(row)["type"] == "stage_usage"]
    assert [row["stage"] for row in usage] == ["scene_context", "initializer_state"]
    assert all(row["agent"] == "initializer" and row["usage"]["output_tokens"] == 20 for row in usage)
    assert len(sessions) == 2
    request = json.loads(sessions[1].queries[0])
    assert request["situation"] == ARGS[-1]
    assert "schema" in request
    for name in ("agnea", "throne"):
        assert (repo / f"cards/{name}.md").read_text() in sessions[1].options.system_prompt
    assert "## Location\nCropdale" in sessions[1].options.system_prompt


@pytest.mark.parametrize("wrapper", ["```json\n{}\n```", "```\n{}\n```",
                                    "Here is the state:\n{}\nReady."])
def test_wrapped_state_validates_first_attempt(repo, state, monkeypatch, wrapper):
    sessions = fake_sdk(monkeypatch, [wrapper.format(json.dumps(state))])
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code == 0, result.output
    assert len(sessions[1].queries) == 1
    assert load_state(Path(result.output.strip())).characters.keys() == state["characters"].keys()


@pytest.mark.parametrize("last_reply", ["not JSON", "[]", '{"places": broken}', "{}"])
def test_invalid_replies_are_traced_and_reported(repo, monkeypatch, last_reply):
    replies = ["First invalid reply", last_reply]
    sessions = fake_sdk(monkeypatch, replies)
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code == 1, result.output
    assert len(sessions[1].queries) == 2
    run, = (repo / "runs").iterdir()
    events = [json.loads(row) for row in (run / "trace.jsonl").read_text().splitlines()]
    failures = [event for event in events if event["type"] == "state_validation_failed"]
    assert [event["attempt"] for event in failures] == [1, 2]
    assert [event["raw_reply"] for event in failures] == replies
    assert all(event["error"] for event in failures)
    assert failures[-1]["error"] in result.output
    assert "Initializer state validation failed after one retry:" in result.output


@pytest.mark.parametrize("failure", ["pydantic", "place", "input_place", "due", "characters"])
@pytest.mark.parametrize("recover", [True, False])
def test_validation_retry(repo, state, monkeypatch, failure, recover):
    bad = copy.deepcopy(state)
    if failure == "pydantic":
        bad["characters"]["agnea"]["goals"] = []
    elif failure == "place":
        bad["places"].append({"slug": "unknown", "details": []})
    elif failure == "input_place":
        bad["places"][0]["slug"] = "unknown"
        for character in bad["characters"].values():
            character["where"] = "unknown"
    elif failure == "due":
        bad["situations"][0]["due"]["day"] = 0
    else:
        del bad["characters"]["throne"]
    sessions = fake_sdk(monkeypatch, [bad, state if recover else bad])
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code == (0 if recover else 1), result.output
    assert len(sessions) == 2
    assert len(sessions[1].queries) == 2
    assert "State validation failed:" in sessions[1].queries[1]
    worlds = list((repo / "worlds").iterdir()) if (repo / "worlds").exists() else []
    assert len(worlds) == (1 if recover else 0)
    run, = (repo / "runs").iterdir()
    assert json.loads((run / "meta.json").read_text())["status"] == ("passed" if recover else "failed")
    failures = [event for row in (run / "trace.jsonl").read_text().splitlines()
                if (event := json.loads(row))["type"] == "state_validation_failed"]
    assert [event["attempt"] for event in failures] == ([1] if recover else [1, 2])
    assert all(event["error"] and event["raw_reply"] == json.dumps(bad) for event in failures)
    if not recover:
        assert failures[-1]["error"] in result.output


def test_dry_run(repo):
    result = CliRunner().invoke(app, ARGS + ["--dry-run"])
    assert result.exit_code == 0, result.output
    run = Path(result.output.strip())
    assert (run / "meta.json").exists() and (run / "trace.jsonl").exists()
    assert json.loads((run / "meta.json").read_text())["status"] == "dry_run"
    assert not (repo / "worlds").exists()


def test_unknown_location(repo):
    args = ARGS.copy()
    args[args.index("--location") + 1] = "unknown"
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1
    assert not (repo / "runs").exists()
    assert not (repo / "worlds").exists()
