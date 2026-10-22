"""Structured output: ClaudeAgentOptions.output_format for every JSON-replying session."""

import asyncio
import json
import shutil
from pathlib import Path

from pydantic import TypeAdapter
from typer.testing import CliRunner

from story_engine.agents import character, curator, initializer, world as world_agent
from story_engine.agents.character import Action, CharacterAgent, CharacterReply, EndOfDay
from story_engine.agents.world import WorldAgent, WorldReply
from story_engine.cli import app
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state

ROOT = Path(__file__).resolve().parents[2]

try:
    import jsonschema
except ImportError:  # pragma: no cover - exercised only when the package is absent
    jsonschema = None


def _assert_schema_accepts(schema, instance, reply_type):
    """Validate `instance` against the session's JSON schema, or the Pydantic union as a fallback."""
    if jsonschema is not None:
        # Union replies are wrapped under "reply" (agents/sdk.json_schema_output).
        jsonschema.validate({"reply": instance} if "reply" in schema.get("properties", {}) else instance, schema)
    else:  # pragma: no cover - exercised only when jsonschema is unavailable
        TypeAdapter(reply_type).validate_python(instance)


class _NullClient:
    """A session that is only ever opened to inspect the options it was built with."""

    def __init__(self, *, options):
        self.options = options

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def query(self, request):
        pass

    async def receive_response(self):
        return
        yield  # pragma: no cover - never reached; makes this an async generator


def test_world_output_format_accepts_all_call_variants(tmp_path, monkeypatch):
    world = tmp_path / 'world'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run = tmp_path / 'run'
    run.mkdir()
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', _NullClient)
    models, settings = load_configs()

    async def exercise():
        async with WorldAgent(ROOT, run, world, models.world,
                              settings.agent_max_turns, TraceWriter(run)) as agent:
            return agent.options

    options = asyncio.run(exercise())
    assert options.output_format['type'] == 'json_schema'
    schema = options.output_format['schema']
    state = load_state(world)
    adjudicate = dict(call='adjudicate',
                      verdicts={slug: dict(status='settled', outcome='Did something.',
                                           where='cropdale', spot=None) for slug in state.characters},
                      encounters=[])
    offscreen = dict(call='offscreen', events=[], people={},
                     situations=[s.model_dump() for s in state.situations],
                     places=[p.model_dump() for p in state.places],
                     situation_notes={s.id: 'Unchanged.' for s in state.situations})
    scene_round = dict(call='scene_round', outcome=None, minor_moves={})
    _assert_schema_accepts(schema, adjudicate, WorldReply)
    _assert_schema_accepts(schema, offscreen, WorldReply)
    _assert_schema_accepts(schema, scene_round, WorldReply)


def test_character_output_format_accepts_both_call_variants(tmp_path, monkeypatch):
    world = tmp_path / 'world'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run = tmp_path / 'run'
    run.mkdir()
    monkeypatch.setattr(character, 'ClaudeSDKClient', _NullClient)
    models, settings = load_configs()
    agent = CharacterAgent(ROOT, run, world, 'throne', models.character,
                           settings.agent_max_turns, TraceWriter(run))

    async def exercise():
        async with agent:
            return agent.options

    options = asyncio.run(exercise())
    assert options.output_format['type'] == 'json_schema'
    schema = options.output_format['schema']
    action = dict(call='action', intent='Find some quiet', move='act', urge=2,
                 action='Throné checks the doorway.', say='')
    end_of_day = dict(call='end_of_day', summary='# Today\nNothing much.')
    _assert_schema_accepts(schema, action, CharacterReply)
    _assert_schema_accepts(schema, end_of_day, CharacterReply)
    assert Action.model_validate(action)
    assert EndOfDay.model_validate(end_of_day)


def test_curator_output_format_is_json_schema(tmp_path, monkeypatch):
    for name in ('config', 'prompts'):
        shutil.copytree(ROOT / name, tmp_path / name)
    world = tmp_path / 'worlds/test'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    from story_engine.world.io import append_event, append_scene, save_state
    from story_engine.world.models import Event, SceneRecord
    append_event(world, Event(id=1, day=1, part='morning', place='cropdale', scene='1',
                             actor='agnea', type='action', content='Agnea waves.',
                             intent='Greet', perceived_by=['agnea']))
    append_scene(world, SceneRecord(id='1', day=1, part='morning', place='cropdale',
                                    participants=['agnea'], first_event_id=1, last_event_id=1,
                                    rounds=1, end='one_left'))
    append_event(world, Event(id=2, day=1, part='evening', place='cropdale', scene='2',
                             actor='agnea', type='action', content='Agnea resolves it.',
                             intent='Resolve', perceived_by=['agnea']))
    append_scene(world, SceneRecord(id='2', day=1, part='evening', place='cropdale',
                                    participants=['agnea'], first_event_id=2, last_event_id=2,
                                    rounds=1, end='one_left'))
    state = load_state(world)
    state.clock.day = 2
    save_state(world, state)
    monkeypatch.chdir(tmp_path)
    options = []

    class Client:
        def __init__(self, **kwargs):
            options.append(kwargs['options'])

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            from claude_agent_sdk import ResultMessage
            episode = dict(acts=[{'scene': '1', 'pov': 'agnea'}, {'scene': '2', 'pov': 'agnea'}],
                           why='A choice.')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(episode))

    monkeypatch.setattr(curator, 'ClaudeSDKClient', Client)
    result = CliRunner().invoke(app, ['world', 'tell', 'test', '--stop-after', 'curate'])
    assert result.exit_code == 0, result.output
    assert len(options) == 1
    assert options[0].output_format['type'] == 'json_schema'
    schema = options[0].output_format['schema']
    if jsonschema is not None:
        jsonschema.validate(
            {'acts': [{'scene': '1', 'pov': 'agnea'}, {'scene': '2', 'pov': 'agnea'}], 'why': 'A choice.'},
            schema,
        )


def test_initializer_state_session_output_format_is_json_schema(tmp_path, monkeypatch):
    for name in ("config/models.yaml", "config/settings.yaml", "prompts/initializer_scene_context.md",
                 "prompts/initializer_state.md", "cards/agnea.md", "cards/throne.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    place = tmp_path / "kb/locations/towns/cropdale.md"
    place.parent.mkdir(parents=True)
    place.write_text("# Cropdale")
    monkeypatch.chdir(tmp_path)

    state = {
        "places": [{"slug": "cropdale", "details": ["festival"]}],
        "characters": {slug: {"where": "cropdale", "goals": ["Visit the festival"], "commitments": []}
                       for slug in ("agnea", "throne")},
        "situations": [{"id": "festival", "summary": "A festival", "touches": ["agnea"],
                        "people": [], "status": "open", "next": "The dancing begins",
                        "due": {"day": 1, "part": "evening"}}],
    }
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
            from claude_agent_sdk import ResultMessage
            text = "## Location\nCropdale" if self.index == 0 else json.dumps(state)
            yield ResultMessage("success", 1, 1, False, 1, "fake", result=text)

    monkeypatch.setattr(initializer, "ClaudeSDKClient", FakeClient)
    args = ["world", "new", "--characters", "agnea,throne", "--location", "cropdale",
            "--situation", "Agnea has brought Throné to a festival here."]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    assert len(sessions) == 2
    assert sessions[1].options.output_format['type'] == 'json_schema'
    schema = sessions[1].options.output_format['schema']
    assert 'clock' not in schema['properties']
    assert 'clock' not in schema['required']
    if jsonschema is not None:
        jsonschema.validate({k: v for k, v in state.items()}, schema)


def test_structured_reply_unwraps_union_wrapper():
    from story_engine.agents.sdk import structured_reply
    assert structured_reply("", {"reply": {"call": "action"}}) == {"call": "action"}
    assert structured_reply("", {"call": "action"}) == {"call": "action"}


def test_kb_hook_allows_structured_output_tool(tmp_path):
    import asyncio
    from story_engine.agents.sdk import KBHooks
    hooks = KBHooks(ROOT, tmp_path, agent='throne', turn=1)
    allowed = asyncio.run(hooks.pre_tool_use({'tool_name': 'StructuredOutput', 'tool_input': {'reply': {}}}, None, {}))
    denied = asyncio.run(hooks.pre_tool_use({'tool_name': 'Bash', 'tool_input': {'command': 'ls'}}, None, {}))
    assert allowed['hookSpecificOutput']['permissionDecision'] == 'allow'
    assert denied['hookSpecificOutput']['permissionDecision'] == 'deny'
    assert asyncio.run(hooks.post_tool_use({'tool_name': 'StructuredOutput', 'tool_input': {}}, None, {})) == {}
