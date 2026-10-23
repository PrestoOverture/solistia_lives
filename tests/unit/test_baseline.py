import json
from pathlib import Path

import pytest
import yaml
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ThinkingBlock, ToolUseBlock
from typer.testing import CliRunner

from story_engine.agents import baseline, initializer
from story_engine.cli import app
from story_engine.runs import RunMeta

ARGS = [
    "generate", "--mode", "baseline", "--characters", "osvald,temenos",
    "--location", "new_delsta", "--scenario", "catching up over drinks at a tavern",
]
CONTEXT = "## Location\nNew Delsta\n## Characters\nOsvald and Temenos\n"
STORY = "# An Unfinished Argument\n\nOsvald raised his glass. ‘To peace.’\n"
USAGE = {"input_tokens": 123, "output_tokens": 45, "cache_read_input_tokens": 100}
COST = 0.123
THOUGHTS = {"initializer": ["Scene\ncontext", "", "乾杯"], "baseline": ["Plan the story.", "🍺\n"]}


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = Path(__file__).resolve().parents[2]
    for name in ("config/models.yaml", "config/settings.yaml"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((source / name).read_bytes())
    for name, text in {
        "prompts/initializer_scene_context.md": "Initializer instructions.",
        "prompts/baseline_writer.md": "Writer instructions.",
        "prompts/style_spec.md": "Style instructions.",
        "cards/osvald.md": "Osvald's identity.",
        "cards/temenos.md": "Temenos's identity.",
        "cards/agnea.md": "Agnea's identity (not in this scene).",
        "kb/locations/brightlands/towns/new_delsta.md": "# New Delsta\n",
    }.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=test-secret\n")

    class FakeInitializer:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, prompt):
            pass

        async def receive_response(self):
            yield ResultMessage("success", 1, 1, False, 1, "initializer", usage=USAGE, result=CONTEXT)

    class UnexpectedWriter:
        def __init__(self, **kwargs):
            pytest.fail("A unit test must install a fake writer")

    monkeypatch.setattr(initializer, "ClaudeSDKClient", FakeInitializer)
    monkeypatch.setattr(baseline, "ClaudeSDKClient", UnexpectedWriter)
    return tmp_path


@pytest.mark.parametrize("thinking", ["off", "adaptive"])
@pytest.mark.parametrize("characters", [["osvald", "temenos"], ["agnea", "temenos", "osvald"]])
@pytest.mark.parametrize("alternate_models", [False, True])
def test_baseline_session(repo: Path, monkeypatch: pytest.MonkeyPatch, thinking: str, characters: list[str], alternate_models: bool) -> None:
    models = yaml.safe_load((repo / "config/models.yaml").read_text())
    model_path = repo / ("alternate_models.yaml" if alternate_models else "config/models.yaml")
    for role, effort in (("initializer", "low"), ("baseline", "max")):
        models[role] = {"model": f"fake-{role}", "effort": effort, "thinking": thinking}
    model_path.write_text(yaml.safe_dump(models))
    settings_path = repo / "config/settings.yaml"
    settings = yaml.safe_load(settings_path.read_text())
    settings.update(words={"min": 1234, "max": 2345}, agent_max_turns=7, scene_context_max_turns=9, writer_max_turns=5)
    settings_path.write_text(yaml.safe_dump(settings))
    calls = []

    class FakeClient:
        def __init__(self, *, options):
            self.options = options
            self.role = "initializer" if options.model == "fake-initializer" else "baseline"
            calls.append((self.role, "init"))
            expected = models[self.role]
            assert options.model == expected["model"]
            assert options.effort == expected["effort"]
            assert options.thinking == {"type": "disabled" if thinking == "off" else "adaptive"}
            assert options.max_turns == (9 if self.role == "initializer" else 5)
            assert options.tools == options.allowed_tools == ["Read", "Grep", "Glob"]
            assert options.setting_sources == [] and options.strict_mcp_config
            assert options.hooks["PreToolUse"][0].matcher is None
            if self.role == "baseline":
                run_dir, = (repo / "runs").iterdir()
                sources = ["prompts/baseline_writer.md", "prompts/style_spec.md"]
                sources += [f"cards/{slug}.md" for slug in characters]
                expected_prompt = "\n\n".join((repo / name).read_text() for name in sources)
                assert options.system_prompt == expected_prompt + "\n\n# Scene context\n\n" + (run_dir / "scene_context.md").read_text()
                if "agnea" not in characters:
                    assert (repo / "cards/agnea.md").read_text() not in options.system_prompt

        async def __aenter__(self):
            calls.append((self.role, "enter"))
            return self

        async def __aexit__(self, *args):
            calls.append((self.role, "exit"))

        async def query(self, prompt):
            calls.append((self.role, "query"))
            expected = {
                "characters": characters, "location": "new_delsta",
                "scenario": "catching up over drinks at a tavern", "kb_path": str(repo / "kb"),
            }
            if self.role == "baseline":
                expected["words"] = settings["words"]
            assert json.loads(prompt) == expected

        async def receive_response(self):
            thoughts = THOUGHTS[self.role] if thinking == "adaptive" else []
            yield AssistantMessage(
                [ThinkingBlock(text, "signature-not-counted") for text in thoughts[:-1]],
                model="fake",
            )
            for tool, inputs in (
                ("Read", {"file_path": str(repo / "kb/locations/brightlands/towns/new_delsta.md")}),
                ("Grep", {"path": str(repo / "kb"), "pattern": "New Delsta"}),
                ("Glob", {"path": str(repo / "kb"), "pattern": "**/*.md"}),
            ):
                reason = f"{self.role} checking {tool}."
                yield AssistantMessage([TextBlock(reason), ToolUseBlock(tool, tool, inputs)], model="fake")
                data = {"tool_name": tool, "tool_input": inputs}
                pre = self.options.hooks["PreToolUse"][0].hooks[0]
                post = self.options.hooks["PostToolUse"][0].hooks[0]
                assert (await pre(data, tool, {}))["hookSpecificOutput"]["permissionDecision"] == "allow"
                await post(data, tool, {})
                blocked = {"tool_name": tool, "tool_input": {"path": str(repo), "file_path": str(repo / ".env")}}
                assert (await pre(blocked, tool, {}))["hookSpecificOutput"]["permissionDecision"] == "deny"
            final = CONTEXT if self.role == "initializer" else "Preamble.\nInline # heading\n## Notes\n\n" + STORY
            yield AssistantMessage(
                [ThinkingBlock(text, "signature-not-counted") for text in thoughts[-1:]]
                + [TextBlock("Intermediate prose is not the final reply.")], model="fake",
            )
            yield ResultMessage("success", 1, 1, False, 4, self.role, usage=USAGE, result=final, total_cost_usd=COST)

    monkeypatch.setattr(initializer, "ClaudeSDKClient", FakeClient)
    monkeypatch.setattr(baseline, "ClaudeSDKClient", FakeClient)
    args = ARGS.copy()
    args[args.index("--characters") + 1] = ",".join(characters)
    if alternate_models:
        args += ["--models", str(model_path)]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    run_dir = Path(result.output.strip())
    assert calls == [(role, event) for role in ("initializer", "baseline") for event in ("init", "enter", "query", "exit")]
    assert (run_dir / "story.md").read_text() == STORY
    meta = RunMeta.model_validate_json((run_dir / "meta.json").read_text())
    assert meta.status == "passed" and meta.error is None
    assert meta.models.model_dump() == {name: {**role, "base_url": None, "auth_token_env": None, "retries": 1, "max_turns": None, "timeout_s": None}
                                        for name, role in models.items()}
    assert meta.models_file == (str(model_path) if alternate_models else "config/models.yaml")
    assert meta.scene_context_from is None
    retrieval = rows(run_dir / "retrieval.jsonl")
    assert [(r["agent"], r["tool"]) for r in retrieval] == [(role, tool) for role in ("initializer", "baseline") for tool in ("Read", "Grep", "Glob")]
    assert all(r["reason"] == f"{r['agent']} checking {r['tool']}." for r in retrieval)
    trace = rows(run_dir / "trace.jsonl")
    assert [(e["type"], e.get("stage")) for e in trace] == [
        ("run_started", None),
        ("stage_started", "scene_context"), ("stage_usage", "scene_context"), ("stage_finished", "scene_context"),
        ("stage_started", "baseline_writer"), ("stage_usage", "baseline_writer"), ("stage_finished", "baseline_writer"),
        ("run_finished", None),
    ]
    assert all(e["usage"] == USAGE for e in trace if e["type"] == "stage_usage")
    assert all(e["total_cost_usd"] == COST for e in trace if e["type"] == "stage_usage")
    for event in (e for e in trace if e["type"] == "stage_usage"):
        thoughts = THOUGHTS[event["agent"]] if thinking == "adaptive" else []
        assert event["thinking_blocks"] == len(thoughts)
        assert event["thinking_chars"] == sum(len(text) for text in thoughts)
    assert "signature-not-counted" not in (run_dir / "trace.jsonl").read_text()
    assert trace[-2]["word_count"] == len(STORY.split())
    assert trace[-1]["status"] == "passed"


@pytest.fixture
def source_run(repo: Path) -> Path:
    result = CliRunner().invoke(app, ARGS + ["--dry-run"])
    assert result.exit_code == 0, result.output
    run_dir = Path(result.output.strip())
    (run_dir / "scene_context.md").write_bytes(
        "## Location\r\nNew Delsta — 乾杯\r\n\r\n## Characters\nOsvald and Temenos".encode("utf-8")
    )
    return run_dir


def test_reused_context_skips_initializer(repo: Path, source_run: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    class UnexpectedInitializer:
        def __init__(self, **kwargs):
            pytest.fail("Reusing context must not start an Initializer session")

    class FakeWriter:
        def __init__(self, *, options):
            calls.append("init")
            assert "# Scene context\n\n" + (source_run / "scene_context.md").read_text() in options.system_prompt

        async def __aenter__(self):
            calls.append("enter")
            return self

        async def __aexit__(self, *args):
            calls.append("exit")

        async def query(self, prompt):
            calls.append("query")

        async def receive_response(self):
            yield ResultMessage("success", 1, 1, False, 1, "writer", usage=USAGE, result=STORY, total_cost_usd=COST)

    monkeypatch.setattr(initializer, "ClaudeSDKClient", UnexpectedInitializer)
    monkeypatch.setattr(baseline, "ClaudeSDKClient", FakeWriter)
    original = (source_run / "scene_context.md").read_bytes()
    result = CliRunner().invoke(app, ARGS + ["--scene-context-from", source_run.name])
    assert result.exit_code == 0, result.output
    run_dir = Path(result.output.strip())
    assert run_dir != source_run
    assert (run_dir / "scene_context.md").read_bytes() == original
    assert (source_run / "scene_context.md").read_bytes() == original
    assert calls == ["init", "enter", "query", "exit"]
    meta = RunMeta.model_validate_json((run_dir / "meta.json").read_text())
    assert meta.scene_context_from == source_run.name
    assert meta.status == "passed"
    trace = rows(run_dir / "trace.jsonl")
    context_events = [e for e in trace if e.get("stage") == "scene_context"]
    assert len(context_events) == 1
    assert context_events[0]["type"] == "stage_reused"
    assert context_events[0]["scene_context_from"] == source_run.name
    assert [e["stage"] for e in trace if e["type"] == "stage_usage"] == ["baseline_writer"]
    usage, = [e for e in trace if e["type"] == "stage_usage"]
    assert usage["thinking_blocks"] == usage["thinking_chars"] == 0


@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("failure", ["missing_source", "missing_context", "characters", "location", "scenario", "missing_meta", "invalid_meta", "stop_after"])
def test_invalid_reuse_creates_no_run(repo: Path, source_run: Path, failure: str, dry_run: bool) -> None:
    source_id = source_run.name
    args = ARGS.copy()
    expected_error = "differ"
    if failure == "missing_source":
        source_id = "missing"
        expected_error = "scene_context.md"
    elif failure == "missing_context":
        (source_run / "scene_context.md").unlink()
        expected_error = "scene_context.md"
    elif failure in ("characters", "location", "scenario"):
        meta_path = source_run / "meta.json"
        meta = json.loads(meta_path.read_text())
        meta["input"][failure] = {
            "characters": ["osvald", "agnea"], "location": "elsewhere", "scenario": "another scene",
        }[failure]
        meta_path.write_text(json.dumps(meta))
    elif failure == "missing_meta":
        (source_run / "meta.json").unlink()
        expected_error = "meta.json"
    elif failure == "invalid_meta":
        (source_run / "meta.json").write_text("{}")
        expected_error = "meta.json"
    elif failure == "stop_after":
        args += ["--stop-after", "scene_context"]
        expected_error = "cannot be combined"
    args += ["--scene-context-from", source_id]
    if dry_run:
        args.append("--dry-run")
    before = set((repo / "runs").iterdir())
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1, result.output
    assert expected_error in result.output
    assert set((repo / "runs").iterdir()) == before


@pytest.mark.parametrize("failure", ["startup", "query", "receive", "exit", "error_result", "agent_max_turns", "empty_result", "missing_result", "no_heading"])
def test_failing_writer_has_no_story(repo: Path, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    class FakeWriter:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            if failure == "startup":
                raise RuntimeError("test-secret startup failure")
            return self

        async def __aexit__(self, *args):
            if failure == "exit":
                raise RuntimeError("test-secret exit failure")

        async def query(self, prompt):
            if failure == "query":
                raise RuntimeError("test-secret query failure")

        async def receive_response(self):
            if failure == "receive":
                raise RuntimeError("test-secret stream failure")
            if failure == "missing_result":
                return
            yield ResultMessage(
                "error_max_turns" if failure == "agent_max_turns" else "success",
                1, 1, failure == "error_result", 1, "writer", usage=USAGE,
                errors=["test-secret\nprivate diagnostic"] if failure == "error_result" else None,
                result="" if failure == "empty_result" else "Inline # title\n## Not a title" if failure == "no_heading" else STORY,
            )

    monkeypatch.setattr(baseline, "ClaudeSDKClient", FakeWriter)
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code == 1
    run_dir, = (repo / "runs").iterdir()
    meta = RunMeta.model_validate_json((run_dir / "meta.json").read_text())
    assert meta.status == "failed" and meta.error.startswith("baseline_writer failed:")
    assert not (run_dir / "story.md").exists()
    assert (run_dir / "scene_context.md").read_text() == CONTEXT
    assert "test-secret" not in result.output
    assert len(result.output.splitlines()) == 1
    for path in run_dir.iterdir():
        assert "test-secret" not in path.read_text()
    trace = rows(run_dir / "trace.jsonl")
    assert trace[-2]["type"] == "stage_failed" and trace[-2]["stage"] == "baseline_writer"
    assert trace[-1]["status"] == "failed"


def test_timeout_fails_run_with_meta_error(repo, monkeypatch):
    import asyncio

    path = repo / 'config/models.yaml'
    models = yaml.safe_load(path.read_text())
    models['baseline']['timeout_s'] = 0.05
    path.write_text(yaml.safe_dump(models))

    class StalledWriter:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            await asyncio.Event().wait()
            yield

    monkeypatch.setattr(baseline, 'ClaudeSDKClient', StalledWriter)
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code != 0
    run_dir, = (repo / 'runs').iterdir()
    meta = RunMeta.model_validate_json((run_dir / 'meta.json').read_bytes())
    assert meta.status == 'failed'
    assert 'timed out after 0.05s' in meta.error
    event, = [row for row in rows(run_dir / 'trace.jsonl') if row['type'] == 'call_timeout']
    assert (event['stage'], event['agent'], event['timeout_s']) == ('baseline_writer', 'baseline', 0.05)
