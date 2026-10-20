import asyncio
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from pydantic import ValidationError

from story_engine.agents import character
from story_engine.agents.character import Action, CharacterAgent
from story_engine.agents.sdk import SessionError
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state
from story_engine.world.models import Event

ROOT = Path(__file__).resolve().parents[2]
VALID = dict(intent="Find some quiet", move="act", urge=2, action="Throné checks the doorway.", say="")


def setup_agent(tmp_path, monkeypatch, replies):
    world = tmp_path / "world"
    shutil.copytree(ROOT / "tests/fixtures/worlds/agnea_throne", world)
    (world / "memory/throne.md").write_text("Yesterday I arrived.")
    run = tmp_path / "run"
    run.mkdir()
    instances = []
    requests = []
    lifecycle = []

    class FakeClient:
        def __init__(self, *, options):
            instances.append(self)
            self.options = options

        async def __aenter__(self):
            lifecycle.append("enter")
            return self

        async def __aexit__(self, *args):
            lifecycle.append("exit")

        async def query(self, request):
            requests.append(request)

        async def receive_response(self):
            hooks = self.options.hooks["PostToolUse"][0].hooks[0]
            await hooks({"tool_name": "Read", "tool_input": {
                "file_path": str(ROOT / "kb/characters/throne/throne.md")}}, "read", {})
            yield ResultMessage("success", 1, 1, False, 1, "fake", usage={"input_tokens": 3}, result=next(replies))

    monkeypatch.setattr(character, "ClaudeSDKClient", FakeClient)
    models, settings = load_configs()
    agent = CharacterAgent(ROOT, run, world, "throne", models.character,
                           settings.turn_cap, TraceWriter(run))
    return agent, instances, requests, lifecycle, run


@pytest.mark.parametrize("fenced", [False, True])
def test_valid_action(tmp_path, monkeypatch, fenced):
    reply = json.dumps(VALID)
    if fenced:
        reply = f"```json\n{reply}\n```"
    agent, instances, requests, lifecycle, run = setup_agent(tmp_path, monkeypatch, iter([reply]))

    async def exercise():
        async with agent:
            return await agent.act([])

    assert asyncio.run(exercise()) == Action(**VALID)
    assert lifecycle == ["enter", "exit"] and len(instances) == 1
    state = load_state(agent.world_dir)
    opening = json.loads(requests[0])
    assert opening == {"clock": state.clock.model_dump(), "place": state.characters["throne"].where,
                       "goals": state.characters["throne"].goals,
                       "commitments": [item.model_dump() for item in state.characters["throne"].commitments],
                       "memory": "Yesterday I arrived.", "perceived": []}
    expected_prompt = "\n\n".join(path.read_text() for path in [
        ROOT / "prompts/character.md", ROOT / "cards/throne.md", agent.world_dir / "scene_context.md"])
    assert instances[0].options.system_prompt == expected_prompt
    assert instances[0].options.model == agent.role.model
    usage = json.loads((run / "trace.jsonl").read_text())
    assert usage["type"] == "stage_usage" and usage["agent"] == "throne" and usage["turn"] == 1
    retrieval = json.loads((run / "retrieval.jsonl").read_text())
    assert retrieval["agent"] == "throne" and retrieval["turn"] == 1


@pytest.mark.parametrize("second_valid", [True, False])
def test_retry(tmp_path, monkeypatch, second_valid):
    bad = json.dumps({**VALID, "intent": " "})
    agent, instances, requests, lifecycle, run = setup_agent(
        tmp_path, monkeypatch, iter([bad, json.dumps(VALID) if second_valid else bad]))

    async def exercise():
        async with agent:
            return await agent.act([])

    if second_valid:
        assert asyncio.run(exercise()) == Action(**VALID)
    else:
        with pytest.raises(SessionError, match="intent must be non-empty"):
            asyncio.run(exercise())
    assert len(requests) == 2 and "intent must be non-empty" in requests[1]
    assert len(instances) == 1 and lifecycle == ["enter", "exit"]
    assert [json.loads(line)["turn"] for line in (run / "trace.jsonl").read_text().splitlines()] == [1, 1]


def test_two_calls_share_session_and_only_send_new_perceptions(tmp_path, monkeypatch):
    agent, instances, requests, lifecycle, run = setup_agent(
        tmp_path, monkeypatch, iter([json.dumps(VALID)] * 2))
    event = Event(id=1, day=1, part="morning", place="cropdale", actor="agnea",
                  type="speech", content="Hello!", intent="private", perceived_by=["throne"])
    unseen = event.model_copy(update={"id": 2, "perceived_by": ["agnea"]})
    new = event.model_copy(update={"id": 3, "content": "Come along."})
    (agent.world_dir / "memory/throne.md").unlink()

    async def exercise():
        async with agent:
            await agent.act([event, unseen])
            await agent.act([event, new])

    asyncio.run(exercise())
    assert len(instances) == 1 and lifecycle == ["enter", "exit"]
    assert "memory" not in json.loads(requests[0])
    assert json.loads(requests[1]) == {"perceived": [new.model_dump(exclude={"intent", "perceived_by"})]}
    assert "private" not in requests[0] and "Hello!" not in requests[1]
    assert [json.loads(line)["turn"] for line in (run / "retrieval.jsonl").read_text().splitlines()] == [1, 2]


@pytest.mark.parametrize("changes,reason", [
    ({"move": "bad"}, "Input should be"),
    ({"urge": 0}, "act urge"),
    ({"urge": 4}, "act urge"),
    ({"action": " ", "say": " "}, "non-empty action or say"),
    ({"move": "wait", "urge": 1}, "urge must be 0"),
    ({"move": "leave", "urge": 2}, "urge must be 0"),
])
def test_action_constraints(changes, reason):
    with pytest.raises(ValidationError, match=reason):
        Action.model_validate({**VALID, **changes})


@pytest.mark.parametrize("move", ["wait", "leave"])
def test_non_act(move):
    assert Action(**{**VALID, "move": move, "urge": 0, "action": ""}).move == move


def test_context_is_required_and_cannot_be_reopened(tmp_path, monkeypatch):
    agent, instances, requests, lifecycle, run = setup_agent(tmp_path, monkeypatch, iter([]))

    async def exercise():
        with pytest.raises(SessionError, match="async context manager"):
            await agent.act([])
        async with agent:
            pass
        with pytest.raises(SessionError, match="only be opened once"):
            async with agent:
                pass

    asyncio.run(exercise())
    assert len(instances) == 1
