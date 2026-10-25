from pathlib import Path
import shutil

import pytest
from typer.testing import CliRunner

from story_engine import cli
from story_engine.agents import sdk
from story_engine.config import ConfigError, Role, load_configs
from story_engine.runs import create_run

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("base_url", ["https://provider.example", None])
@pytest.mark.parametrize("thinking", ["off", "adaptive", None])
def test_provider_explicit_disabled_thinking_body(tmp_path, monkeypatch, base_url, thinking):
    captured = {}
    monkeypatch.setattr(sdk, "ClaudeAgentOptions", lambda **kwargs: captured.update(kwargs))
    hooks = sdk.KBHooks(tmp_path, tmp_path, "test", 0)
    role = Role(model="test", effort=None, base_url=base_url, thinking=thinking)

    sdk.session_options(tmp_path, tmp_path, role, "", 1, hooks)

    if base_url and thinking == "off":
        assert captured["env"]["CLAUDE_CODE_EXTRA_BODY"] == '{"thinking":{"type":"disabled"}}'
    else:
        assert "CLAUDE_CODE_EXTRA_BODY" not in captured["env"]


@pytest.mark.parametrize("source", ["dotenv", "environ"])
def test_provider_environment_and_null_options(tmp_path, monkeypatch, source):
    model_variables = (
        "ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL",
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://default.example")
    monkeypatch.setenv("TEST_PROVIDER_KEY", "fake-process")
    if source == "dotenv":
        (tmp_path / ".env").write_text("TEST_PROVIDER_KEY='fake-file'\n")
    captured = {}
    monkeypatch.setattr(sdk, "ClaudeAgentOptions", lambda **kwargs: captured.update(kwargs))
    hooks = sdk.KBHooks(tmp_path, tmp_path, "test", 0)
    role = Role(model="test", effort=None, thinking=None,
                base_url="https://provider.example", auth_token_env="TEST_PROVIDER_KEY")
    sdk.session_options(tmp_path, tmp_path, role, "", 1, hooks)
    assert captured["env"]["ANTHROPIC_BASE_URL"] == role.base_url
    assert captured["env"]["ANTHROPIC_AUTH_TOKEN"] == (
        "fake-file" if source == "dotenv" else "fake-process")
    assert "ANTHROPIC_API_KEY" not in captured["env"]
    for key in model_variables:
        assert captured["env"][key] == role.model
    assert "effort" not in captured and "thinking" not in captured

    role = Role(model="test", effort="high", thinking="off")
    sdk.session_options(tmp_path, tmp_path, role, "", 1, hooks)
    for key in model_variables:
        assert key not in captured["env"]
    assert captured["env"] == {
        **sdk.session_environment(tmp_path),
        "CLAUDE_CONFIG_DIR": str((tmp_path / ".sdk").resolve()),
    }
    assert captured["effort"] == "high"
    assert captured["thinking"] == {"type": "disabled"}


def test_spark_config_and_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    models, _ = load_configs("config/models_spark.yaml")
    original, _ = load_configs()
    for name in type(models).model_fields:
        role = getattr(models, name)
        assert role.model == "spark-x2.6"
        assert role.base_url == "https://maas-api.cn-huabei-1.xf-yun.com/anthropic"
        assert role.auth_token_env == "SPARK_API_KEY"
        assert (role.effort, role.thinking) == (
            getattr(original, name).effort, getattr(original, name).thinking)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SPARK_API_KEY", "fake-secret")
    run = create_run([], "", "", "initializer", None, models)
    text = (run / "meta.json").read_text()
    assert "fake-secret" not in text
    from story_engine.runs import RunMeta
    meta = RunMeta.model_validate_json(text)
    assert meta.models == models


@pytest.mark.parametrize("command", [
    ["world", "new", "--characters", "agnea,throne", "--location", "cropdale", "--situation", "test"],
    ["world", "run", "sample"],
    ["world", "tell", "sample"],
    ["eval", "world", "sample"],
])
def test_commands_use_models(tmp_path, monkeypatch, command):
    shutil.copytree(ROOT / "tests/fixtures/worlds/agnea_throne", tmp_path / "worlds/sample")
    monkeypatch.chdir(tmp_path)
    calls = []

    def load(path):
        calls.append(path)
        raise ConfigError("selected models")

    monkeypatch.setattr(cli, "load_configs", load)
    from story_engine.eval import world
    monkeypatch.setattr(world, "load_configs", load)
    result = CliRunner().invoke(cli.app, command + ["--models", "alternate.yaml"])
    assert result.exit_code == 1
    assert calls == [Path("alternate.yaml")], result.output


def test_simulation_session_loads_selected_models(tmp_path, monkeypatch):
    import asyncio
    import json
    from story_engine import simulation

    (tmp_path / "genesis.json").touch()
    (tmp_path / "meta.json").write_text(json.dumps({"models_file": "alternate.yaml"}))
    calls = []

    def load(path):
        calls.append(path)
        raise ConfigError("selected models")

    monkeypatch.setattr(simulation, "load_configs", load)
    session = simulation.TickSession(tmp_path, tmp_path, root=tmp_path)
    with pytest.raises(ConfigError, match="selected models"):
        asyncio.run(session.__aenter__())
    assert calls == [tmp_path / "alternate.yaml"]
