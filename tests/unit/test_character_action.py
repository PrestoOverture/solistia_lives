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
VALID = dict(call="action", intent="Find some quiet", move="act", urge=2,
            action="Throné checks the doorway.", say="")


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
                           settings.agent_max_turns, TraceWriter(run))
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
                       "memory": "Yesterday I arrived.", "perceived": [],
                       "call": "scene_move", "reply": "JSON with call: 'action'"}
    expected_prompt = "\n\n".join(path.read_text() for path in [
        ROOT / "prompts/character.md", ROOT / "cards/throne.md", agent.world_dir / "scene_context.md"])
    assert instances[0].options.system_prompt == expected_prompt
    assert instances[0].options.model == agent.role.model
    usage = json.loads((run / "trace.jsonl").read_text())
    assert usage["type"] == "stage_usage" and usage["agent"] == "throne" and usage["turn"] == 1
    retrieval = json.loads((run / "retrieval.jsonl").read_text())
    assert retrieval["agent"] == "throne" and retrieval["turn"] == 1


def test_overlong_action_rejected_then_retried(tmp_path, monkeypatch):
    """A 181-char action fails the schema length cap and is rejected, then retried."""
    too_long = "a" * 181
    bad = json.dumps({**VALID, "action": too_long})
    agent, instances, requests, lifecycle, run = setup_agent(
        tmp_path, monkeypatch, iter([bad, json.dumps(VALID)]))

    async def exercise():
        async with agent:
            return await agent.act([])

    assert asyncio.run(exercise()) == Action(**VALID)
    assert len(requests) == 2 and "at most 180 characters" in requests[1]


def test_overlong_say_rejected_then_retried(tmp_path, monkeypatch):
    """A 401-char say fails the schema length cap and is rejected, then retried."""
    too_long = "a" * 401
    bad = json.dumps({**VALID, "action": "", "say": too_long})
    agent, instances, requests, lifecycle, run = setup_agent(
        tmp_path, monkeypatch, iter([bad, json.dumps(VALID)]))

    async def exercise():
        async with agent:
            return await agent.act([])

    assert asyncio.run(exercise()) == Action(**VALID)
    assert len(requests) == 2 and "at most 400 characters" in requests[1]


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
    assert json.loads(requests[1]) == {"self": load_state(agent.world_dir).characters[agent.slug].model_dump(),
                                     "perceived": [new.model_dump(exclude={"intent", "perceived_by"})],
                                       "call": "scene_move", "reply": "JSON with call: 'action'"}
    assert "private" not in requests[0] and "Hello!" not in requests[1]
    assert [json.loads(line)["turn"] for line in (run / "retrieval.jsonl").read_text().splitlines()] == [1, 2]


def test_character_input_excludes_op_only_events_and_keeps_visible_ops(tmp_path, monkeypatch):
    from story_engine.world.io import commit_event, read_events
    from story_engine.world.ops import ClockOp, Promise
    from story_engine.world.permissions import Authority
    agent, _, requests, _, _ = setup_agent(tmp_path, monkeypatch, iter([json.dumps(VALID)]))
    commit_event(agent.world_dir, Event(
        id=0, day=1, part='morning', place='cropdale', actor='world', type='state_change',
        content='', perceived_by=['throne'], ops=[ClockOp(day=1, part='morning')]))
    visible = commit_event(agent.world_dir, Event(
        id=0, day=1, part='morning', place='cropdale', actor='agnea', type='speech',
        content='Agnea promises to return.', intent='A private reason', perceived_by=['throne'],
        scene='1', round=1, ops=[Promise(who='agnea', what='Return', where='cropdale', day=1, part='night')]),
        authority=Authority('character_scene', 'agnea'))

    async def exercise():
        async with agent:
            await agent.act(read_events(agent.world_dir))

    asyncio.run(exercise())
    perceived = json.loads(requests[0])['perceived']
    assert [row['id'] for row in perceived] == [visible.id]
    assert perceived[0]['ops'] == [op.model_dump() for op in visible.ops]
    assert 'intent' not in perceived[0] and 'perceived_by' not in perceived[0]


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


@pytest.mark.parametrize("text", [
    'Throné follows her out.',
    'Agnea and Throné leave together.',
    '"Throné, wait!" Agnea calls.',
])
def test_character_action_text_not_judged(tmp_path, monkeypatch, text):
    """D27: code never judges an action's wording, including whether it names another
    main character as its subject."""
    agent, _, requests, _, _ = setup_agent(
        tmp_path, monkeypatch, iter([json.dumps({**VALID, 'action': text})]))
    agent.slug = 'agnea'

    async def exercise():
        async with agent:
            return await agent.act([])

    result = asyncio.run(exercise())
    assert len(requests) == 1
    assert result.action == text


def test_structured_output_only_reply_is_accepted(tmp_path, monkeypatch):
    """A reply delivered only via `structured_output`, with `result` empty, is accepted."""
    world = tmp_path / "world"
    shutil.copytree(ROOT / "tests/fixtures/worlds/agnea_throne", world)
    run = tmp_path / "run"
    run.mkdir()

    class FakeClient:
        def __init__(self, *, options):
            self.options = options

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            yield ResultMessage("success", 1, 1, False, 1, "fake", result="", structured_output=VALID)

    monkeypatch.setattr(character, "ClaudeSDKClient", FakeClient)
    models, settings = load_configs()
    agent = CharacterAgent(ROOT, run, world, "throne", models.character,
                           settings.agent_max_turns, TraceWriter(run))

    async def exercise():
        async with agent:
            return await agent.act([])

    assert asyncio.run(exercise()) == Action(**VALID)


def test_summarize_from_structured_end_of_day_reply(tmp_path, monkeypatch):
    """`summarize` returns the `summary` string from an `end_of_day` structured reply and writes it to memory."""
    world = tmp_path / "world"
    shutil.copytree(ROOT / "tests/fixtures/worlds/agnea_throne", world)
    run = tmp_path / "run"
    run.mkdir()
    summary = "# Today\nWalked the festival grounds.\n## Changed\nNothing yet.\n## Wants\nQuiet."

    class FakeClient:
        def __init__(self, *, options):
            self.options = options

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            yield ResultMessage("success", 1, 1, False, 1, "fake", result="",
                               structured_output={"call": "end_of_day", "summary": summary})

    monkeypatch.setattr(character, "ClaudeSDKClient", FakeClient)
    models, settings = load_configs()
    agent = CharacterAgent(ROOT, run, world, "throne", models.character,
                           settings.agent_max_turns, TraceWriter(run))

    async def exercise():
        async with agent:
            return await agent.summarize([])

    result = asyncio.run(exercise())
    assert result == summary
    from story_engine.world.io import write_memory
    write_memory(world, "throne", result)
    assert (world / "memory/throne.md").read_text() == summary


def test_choose_returns_plan(tmp_path, monkeypatch):
    """A part-of-day choice is a Plan (D26), not a scene Action."""
    world = tmp_path / "world"
    shutil.copytree(ROOT / "tests/fixtures/worlds/agnea_throne", world)
    run = tmp_path / "run"
    run.mkdir()
    plan = dict(call="plan", kind="go", intent="Find somewhere quiet", where="cropdale",
               spot="the tavern's upper floor", aim="Walk to the tavern and look around.")

    class FakeClient:
        def __init__(self, *, options):
            self.options = options

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            yield ResultMessage("success", 1, 1, False, 1, "fake", result="", structured_output=plan)

    monkeypatch.setattr(character, "ClaudeSDKClient", FakeClient)
    models, settings = load_configs()

    async def choose():
        async with CharacterAgent(ROOT, run, world, "throne", models.character,
                                  settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.choose("morning", [])

    result = asyncio.run(choose())
    assert result == character.Plan(**plan)


def test_plan_aim_over_max_length_rejected_then_retried(tmp_path, monkeypatch):
    """`aim` fails its schema length cap at 141 chars and is rejected, then retried."""
    too_long = "a" * 141
    bad = dict(call="plan", kind="go", intent="Find somewhere quiet", where="cropdale", spot=None, aim=too_long)
    good = dict(call="plan", kind="go", intent="Find somewhere quiet", where="cropdale", spot=None, aim="Walk to the tavern.")
    agent, instances, requests, lifecycle, run = setup_agent(
        tmp_path, monkeypatch, iter([json.dumps(bad), json.dumps(good)]))

    async def exercise():
        async with agent:
            return await agent.choose("morning", [])

    assert asyncio.run(exercise()) == character.Plan(**good)
    assert len(requests) == 2 and "at most 140 characters" in requests[1]


def test_scene_move_request_names_its_reply_type(tmp_path, monkeypatch):
    """The character session allows plan|action|end_of_day; a scene move must ask for an action."""
    world = tmp_path / "world"
    shutil.copytree(ROOT / "tests/fixtures/worlds/agnea_throne", world)
    run = tmp_path / "run"
    run.mkdir()
    requests = []

    class FakeClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            requests.append(json.loads(request))

        async def receive_response(self):
            yield ResultMessage("success", 1, 1, False, 1, "fake", result="", structured_output=VALID)

    monkeypatch.setattr(character, "ClaudeSDKClient", FakeClient)
    models, settings = load_configs()

    async def exercise():
        async with CharacterAgent(ROOT, run, world, "throne", models.character,
                                  settings.agent_max_turns, TraceWriter(run)) as agent:
            await agent.act([])

    asyncio.run(exercise())
    assert requests[0]["call"] == "scene_move"
    assert "'action'" in requests[0]["reply"]
