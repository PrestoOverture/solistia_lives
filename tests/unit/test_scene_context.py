import asyncio
import json
import os
from pathlib import Path

import pytest
import yaml
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock, UserMessage
from typer.testing import CliRunner

from story_engine.agents import baseline, initializer
from story_engine.agents.sdk import KBHooks, session_environment
from story_engine.cli import app
from story_engine.runs import RunMeta

ARGS = [
    "generate", "--mode", "baseline", "--stop-after", "scene_context",
    "--characters", "osvald,temenos", "--location", "new_delsta",
    "--scenario", "catching up over drinks at a tavern",
]
FINAL = "## Location\nNew Delsta\n## Characters\nOsvald and Temenos — 乾杯\n"
USAGE = {"input_tokens": 123, "output_tokens": 45, "cache_read_input_tokens": 100}


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = Path(__file__).resolve().parents[2]
    for name in ("config/models.yaml", "config/settings.yaml", "prompts/initializer_scene_context.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((source / name).read_bytes())
    for name in ("locations/brightlands/towns/new_delsta.md", "characters/osvald/osvald.md"):
        path = tmp_path / "kb" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Canon\n")
    monkeypatch.chdir(tmp_path)
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text("ANTHROPIC_API_KEY=test-credential\nANTHROPIC_BASE_URL=https://relay.invalid\n")

    class UnexpectedClient:
        def __init__(self, **kwargs):
            pytest.fail("A unit test must install a fake SDK client")

    monkeypatch.setattr(initializer, "ClaudeSDKClient", UnexpectedClient)
    monkeypatch.setattr(baseline, "ClaudeSDKClient", UnexpectedClient)
    return tmp_path


@pytest.fixture
def hooks(repo: Path) -> KBHooks:
    run_dir = repo / "runs/test"
    run_dir.mkdir(parents=True)
    return KBHooks(repo, run_dir, "initializer", 0)


def hook_data(tool: str, inputs: dict, tool_id: str = "call-1") -> dict:
    return {"tool_name": tool, "tool_input": inputs, "tool_use_id": tool_id}


@pytest.mark.parametrize("tool,inputs,expected", [
    ("Read", {"file_path": "kb/characters/osvald/osvald.md"}, "characters/osvald/osvald.md"),
    ("Grep", {"path": "kb/characters", "pattern": "Osvald"}, "characters"),
    ("Glob", {"path": "kb", "pattern": "**/new_delsta.md"}, "."),
])
def test_kb_access_is_allowed_and_logged(hooks: KBHooks, tool: str, inputs: dict, expected: str) -> None:
    reason = "I need the canon for this scene."
    hooks.observe(AssistantMessage(content=[TextBlock(reason), ToolUseBlock("call-1", tool, inputs)], model="fake"))
    data = hook_data(tool, inputs)
    answer = asyncio.run(hooks.pre_tool_use(data, "call-1", {}))["hookSpecificOutput"]
    assert answer["permissionDecision"] == "allow"
    assert Path(answer["updatedInput"]["file_path" if tool == "Read" else "path"]).is_absolute()
    asyncio.run(hooks.post_tool_use(data, "call-1", {}))
    assert rows(hooks.log) == [{"turn": 0, "agent": "initializer", "tool": tool, "file": expected, "reason": reason}]


@pytest.mark.parametrize("tool,inputs", [
    ("Read", {"file_path": "/etc/passwd"}),
    ("Read", {"file_path": "kb/../.env"}),
    ("Read", {"file_path": "kb/leak.md"}),
    ("Read", {"file_path": "kb-other/file.md"}),
    ("Read", {}),
    ("Read", {"file_path": ""}),
    ("Read", {"file_path": 7}),
    ("Grep", {"pattern": "anything"}),
    ("Glob", {"pattern": "kb/**/*.md"}),
    ("Grep", {"path": "..", "pattern": "anything"}),
    ("Glob", {"path": "/etc", "pattern": "*"}),
    ("Glob", {"path": "kb", "pattern": "../*"}),
    ("Glob", {"path": "kb", "pattern": "/etc/*"}),
    ("Glob", {"path": "kb", "pattern": "{../*,*.md}"}),
    ("Grep", {"path": "kb", "pattern": ".", "glob": "../*"}),
    ("Write", {"file_path": "kb/new.md", "content": "overwrite"}),
    ("Edit", {"file_path": "kb/characters/osvald/osvald.md"}),
    ("Bash", {"command": "cat kb/README.md"}),
    ("Agent", {"prompt": "read canon"}),
    ("WebFetch", {"url": "https://example.com"}),
    ("UnknownTool", {"path": "kb"}),
])
def test_disallowed_access(hooks: KBHooks, repo: Path, tool: str, inputs: dict) -> None:
    (repo / "kb/leak.md").symlink_to(repo / ".env")
    response = asyncio.run(hooks.pre_tool_use(hook_data(tool, inputs), "call-1", {}))
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not rows(hooks.log)


@pytest.mark.parametrize("tool", ["Grep", "Glob"])
def test_search_cannot_follow_escaping_symlink(hooks: KBHooks, repo: Path, tool: str) -> None:
    (repo / "kb/linked").symlink_to(repo / "config", target_is_directory=True)
    response = asyncio.run(hooks.pre_tool_use(hook_data(tool, {"path": "kb", "pattern": "*"}), None, {}))
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_canonical_paths_and_append_only_retrieval(hooks: KBHooks, repo: Path) -> None:
    (repo / "kb/alias.md").symlink_to(repo / "kb/characters/osvald/osvald.md")
    for name in ("kb/alias.md", "kb/characters/../characters/osvald/osvald.md"):
        data = hook_data("Read", {"file_path": name})
        assert asyncio.run(hooks.pre_tool_use(data, None, {}))["hookSpecificOutput"]["permissionDecision"] == "allow"
        original = hooks.log.read_bytes()
        asyncio.run(hooks.post_tool_use(data, None, {}))
        assert hooks.log.read_bytes().startswith(original)
    assert len(rows(hooks.log)) == 2
    assert all(row["file"] == "characters/osvald/osvald.md" and row["reason"] is None for row in rows(hooks.log))


def test_reasons_follow_tool_ids_and_do_not_leak_between_turns(hooks: KBHooks) -> None:
    inputs = {"file_path": "kb/characters/osvald/osvald.md"}
    hooks.observe(AssistantMessage([TextBlock("First reason.")], model="fake", message_id="a"))
    hooks.observe(AssistantMessage([ToolUseBlock("first", "Read", inputs)], model="fake", message_id="a"))
    hooks.observe(AssistantMessage([TextBlock("Second reason."), ToolUseBlock("second", "Read", inputs)], model="fake", message_id="a"))
    hooks.observe(UserMessage(content=[]))
    hooks.observe(AssistantMessage([ToolUseBlock("third", "Read", inputs)], model="fake", message_id="b"))
    for tool_id in ("second", "first", "third"):
        asyncio.run(hooks.post_tool_use(hook_data("Read", inputs, tool_id), tool_id, {}))
    assert [row["reason"] for row in rows(hooks.log)] == ["Second reason.", "First reason.", None]


@pytest.mark.parametrize("mode", ["baseline"])
@pytest.mark.parametrize("preamble", ["", "Here is the scene context.\n# Summary\nInline ## heading\n\n"])
@pytest.mark.parametrize("base_source,expected_host", [
    ("dotenv", "relay.invalid"),
    ("inherited", "inherited.invalid"),
    ("unset", "api.anthropic.com"),
])
def test_scene_context_session(
    repo: Path, monkeypatch: pytest.MonkeyPatch, mode: str, preamble: str,
    base_source: str, expected_host: str,
) -> None:
    calls = []
    if base_source == "dotenv":
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
        (repo / ".env").write_text(
            "ANTHROPIC_API_KEY=test-credential\n"
            "ANTHROPIC_BASE_URL=https://test-user:test-password@relay.invalid:8443/v1?token=test-token#fragment\n"
        )
    else:
        (repo / ".env").write_text("ANTHROPIC_API_KEY=test-credential\n")
        if base_source == "inherited":
            monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://inherited.invalid")
    inherited_env = dict(os.environ)

    class FakeClient:
        def __init__(self, *, options):
            self.options = options
            calls.append("init")
            role = yaml.safe_load((repo / "config/models.yaml").read_text())["initializer"]
            assert options.cwd == repo
            assert options.system_prompt == (repo / "prompts/initializer_scene_context.md").read_text()
            assert options.model == role["model"] and options.effort == role["effort"]
            assert options.thinking == {"type": "disabled"}
            assert options.max_turns == 20
            assert options.tools == options.allowed_tools == ["Read", "Grep", "Glob"]
            assert options.setting_sources == []
            assert options.strict_mcp_config and options.verbatim_prompts
            assert options.env["ANTHROPIC_API_KEY"] == "test-credential"
            assert options.env == {
                **session_environment(repo), "CLAUDE_CONFIG_DIR": options.env["CLAUDE_CONFIG_DIR"],
            }
            assert Path(options.env["CLAUDE_CONFIG_DIR"]).is_relative_to(repo / "runs")
            assert options.extra_args == {"no-session-persistence": None}
            assert options.hooks["PreToolUse"][0].matcher is None  # Catch every tool.
            assert "ANTHROPIC_API_KEY" not in os.environ

        async def __aenter__(self):
            calls.append("enter")
            return self

        async def __aexit__(self, *args):
            calls.append("exit")

        async def query(self, prompt):
            calls.append("query")
            request = json.loads(prompt)
            assert request == {
                "characters": ["osvald", "temenos"], "location": "new_delsta",
                "scenario": "catching up over drinks at a tavern", "kb_path": str(repo / "kb"),
            }
            meta = RunMeta.model_validate_json(next((repo / "runs").glob("*/meta.json")).read_text())
            assert meta.status == "running"
            assert meta.api_host == expected_host

        async def receive_response(self):
            inputs = {"file_path": str(repo / "kb/characters/osvald/osvald.md")}
            yield AssistantMessage([TextBlock("I need Osvald's history."), ToolUseBlock("read-1", "Read", inputs)], model="fake")
            data = hook_data("Read", inputs, "read-1")
            pre = self.options.hooks["PreToolUse"][0].hooks[0]
            post = self.options.hooks["PostToolUse"][0].hooks[0]
            assert (await pre(data, "read-1", {}))["hookSpecificOutput"]["permissionDecision"] == "allow"
            await post(data, "read-1", {})
            yield AssistantMessage([TextBlock(FINAL)], model="fake")
            yield ResultMessage("success", 100, 90, False, 2, "test-session", usage=USAGE, result=preamble + FINAL)

    monkeypatch.setattr(initializer, "ClaudeSDKClient", FakeClient)
    args = ARGS.copy()
    args[args.index("--mode") + 1] = mode
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    run_dir = Path(result.output.strip())
    assert calls == ["init", "enter", "query", "exit"]
    assert (run_dir / "scene_context.md").read_text() == FINAL
    meta = RunMeta.model_validate_json((run_dir / "meta.json").read_text())
    assert meta.status == "stopped" and meta.error is None and meta.mode == mode
    raw_meta = (run_dir / "meta.json").read_text()
    assert json.loads(raw_meta)["api_host"] == expected_host
    for private_value in ("test-credential", "test-user", "test-password", "test-token"):
        assert private_value not in raw_meta
    environment_unchanged = dict(os.environ) == inherited_env
    assert environment_unchanged
    retrieval = rows(run_dir / "retrieval.jsonl")
    assert retrieval == [{"turn": 0, "agent": "initializer", "tool": "Read", "file": "characters/osvald/osvald.md", "reason": "I need Osvald's history."}]
    trace = rows(run_dir / "trace.jsonl")
    assert [row["type"] for row in trace] == ["run_started", "stage_started", "stage_usage", "stage_finished", "run_finished"]
    assert trace[2]["usage"] == USAGE and trace[2]["stage"] == "scene_context"
    assert trace[2]["thinking_blocks"] == trace[2]["thinking_chars"] == 0
    assert trace[-1]["status"] == "stopped"


@pytest.mark.parametrize("failure", ["startup", "query", "receive", "error_result", "turn_cap", "empty_result", "missing_result", "no_heading"])
def test_session_failures_mark_meta_failed(repo: Path, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    class FakeClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            if failure == "startup":
                raise RuntimeError("test-credential\nprivate relay diagnostic")
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, prompt):
            if failure == "query":
                raise RuntimeError("test-credential\nquery failed")

        async def receive_response(self):
            if failure == "receive":
                raise RuntimeError("test-credential\nstream failed")
            if failure == "missing_result":
                return
            yield ResultMessage(
                "error_max_turns" if failure == "turn_cap" else "success",
                1, 1, failure in ("turn_cap", "error_result"), 1, "test-session",
                usage=USAGE, result=("" if failure == "empty_result" else
                                    "# Location\nInline ## Location\n### Characters\n"
                                    if failure == "no_heading" else "test-credential"),
            )

    monkeypatch.setattr(initializer, "ClaudeSDKClient", FakeClient)
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code == 1
    run_dir, = (repo / "runs").iterdir()
    meta = RunMeta.model_validate_json((run_dir / "meta.json").read_text())
    assert meta.status == "failed"
    assert meta.error.startswith("scene_context failed: ")
    if failure == "no_heading":
        assert "no '## ' heading" in meta.error
    assert len(meta.error.splitlines()) == 1
    assert len(result.output.splitlines()) == 1
    assert "test-credential" not in result.output
    for path in run_dir.iterdir():
        assert "test-credential" not in path.read_text()
    assert not (run_dir / "scene_context.md").exists()
    events = rows(run_dir / "trace.jsonl")
    assert events[-2]["type"] == "stage_failed" and events[-1]["status"] == "failed"


@pytest.mark.parametrize("stage", ["beat_plan", "transcript"])
@pytest.mark.parametrize("dry_run", [False, True])
def test_baseline_rejects_pipeline_stops(repo: Path, stage: str, dry_run: bool) -> None:
    args = ARGS.copy()
    args[args.index("--stop-after") + 1] = stage
    result = CliRunner().invoke(app, args + (["--dry-run"] if dry_run else []))
    assert result.exit_code == 2
    assert "Invalid value" in result.output
    assert not (repo / "runs").exists()


@pytest.mark.parametrize("mode", ["baseline"])
@pytest.mark.parametrize("stop_after", [None, "scene_context"])
def test_dry_run_does_not_start_sdk(repo: Path, mode: str, stop_after: str | None) -> None:
    args = ARGS.copy()
    args[args.index("--mode") + 1] = mode
    if stop_after is None:
        index = args.index("--stop-after")
        del args[index:index + 2]
    result = CliRunner().invoke(app, args + ["--dry-run"])
    assert result.exit_code == 0, result.output
    run_dir = Path(result.output.strip())
    assert {path.name for path in run_dir.iterdir()} == {"meta.json", "trace.jsonl"}
    assert RunMeta.model_validate_json((run_dir / "meta.json").read_text()).status == "dry_run"


def test_scene_context_validates_before_creating_run(repo: Path) -> None:
    args = ARGS.copy()
    args[args.index("--location") + 1] = "missing"
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 1 and not (repo / "runs").exists()


def test_dotenv_quotes_comments_export_and_environment_precedence(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (repo / ".env").write_text(
        '# Comment\nexport ANTHROPIC_API_KEY = "file-secret" # comment\n'
        "ANTHROPIC_BASE_URL='https://relay.invalid/v1?a=b#fragment'\n"
        "UNRELATED=value\n"
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "existing-secret")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    assert session_environment(repo) == {
        "ANTHROPIC_API_KEY": "file-secret",
        "ANTHROPIC_BASE_URL": "https://relay.invalid/v1?a=b#fragment",
    }
    assert os.environ["ANTHROPIC_API_KEY"] == "existing-secret"
    assert os.environ["ANTHROPIC_BASE_URL"] == "https://api.anthropic.com"
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert session_environment(repo)["ANTHROPIC_API_KEY"] == "file-secret"
    (repo / ".env").unlink()
    assert session_environment(repo) == {"ANTHROPIC_BASE_URL": "https://api.anthropic.com"}


@pytest.mark.parametrize("key", ["ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"])
@pytest.mark.parametrize("dotenv_value", [None, ""])
def test_dotenv_missing_key_inherits_but_empty_value_overrides(
    repo: Path, monkeypatch: pytest.MonkeyPatch, key: str, dotenv_value: str | None,
) -> None:
    monkeypatch.setenv(key, "inherited-value")
    (repo / ".env").write_text("# No assignments\n" if dotenv_value is None else f"{key}=\n")
    assert session_environment(repo) == {key: "inherited-value" if dotenv_value is None else ""}
    assert os.environ[key] == "inherited-value"
