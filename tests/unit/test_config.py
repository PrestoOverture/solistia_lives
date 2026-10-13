import hashlib
import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.runs import RunMeta


ARGS = ["generate", "--dry-run", "--characters", "osvald,temenos", "--location", "new_delsta", "--scenario", "x", "--mode", "baseline"]
KEYS = [
    ("models.yaml", (role,) if key is None else (role, key))
    for role in ("director", "character", "rewrite", "baseline", "validator")
    for key in (None, "model", "effort")
] + [
    ("settings.yaml", path)
    for path in (("words",), ("words", "min"), ("words", "max"), ("turn_cap",), ("validation_rounds",), ("default_stop",))
]


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = Path(__file__).resolve().parents[2] / "config"
    target = tmp_path / "config"
    target.mkdir()
    for name in ("models.yaml", "settings.yaml"):
        (target / name).write_text((source / name).read_text())
    monkeypatch.chdir(tmp_path)
    return target


@pytest.mark.parametrize("filename,path", KEYS)
def test_every_missing_key_fails(config_dir: Path, filename: str, path: tuple[str, ...]) -> None:
    file = config_dir / filename
    data = yaml.safe_load(file.read_text())
    parent = data
    for part in path[:-1]:
        parent = parent[part]
    parent.pop(path[-1])
    file.write_text(yaml.safe_dump(data))
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code != 0
    assert f"config/{filename}: {'.'.join(path)}:" in result.output
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert not (config_dir.parent / "runs").exists()


@pytest.mark.parametrize("filename,change,key", [
    ("models.yaml", ("director", "extra", "x"), "extra"),
    ("models.yaml", ("director", "effort", "ultra"), "effort"),
    ("settings.yaml", ("default_stop", "fixed:0"), "default_stop"),
    ("settings.yaml", ("words", "min", 3000), "words"),
])
def test_invalid_values(config_dir: Path, filename: str, change: tuple, key: str) -> None:
    file = config_dir / filename
    data = yaml.safe_load(file.read_text())
    parent = data
    for part in change[:-2]:
        parent = parent[part]
    parent[change[-2]] = change[-1]
    file.write_text(yaml.safe_dump(data))
    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code != 0
    assert key in result.output
    assert "Traceback" not in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert not (config_dir.parent / "runs").exists()


def test_valid_dry_run(config_dir: Path) -> None:
    scenario = 'Throné\'s "toast" — 乾杯'
    args = ARGS.copy()
    args[args.index("--scenario") + 1] = scenario
    expected_models = yaml.safe_load((config_dir / "models.yaml").read_text())
    default_stop = yaml.safe_load((config_dir / "settings.yaml").read_text())["default_stop"]
    run_dirs = []
    for extra, expected_stop in (([], default_stop), (["--stop", "fixed:6"], "fixed:6")):
        result = CliRunner().invoke(app, args + extra)
        assert result.exit_code == 0
        run_dir = Path(result.output.strip())
        assert run_dir.parent == Path("runs")
        assert run_dir.is_dir()
        raw = (run_dir / "meta.json").read_bytes()
        assert "Throné".encode("utf-8") in raw
        assert "乾杯".encode("utf-8") in raw
        meta = RunMeta.model_validate(json.loads(raw))
        assert meta.run_id == run_dir.name
        assert meta.input.scenario.encode("utf-8") == scenario.encode("utf-8")
        assert meta.input.characters == ["osvald", "temenos"]
        assert meta.status == "dry_run"
        assert meta.models.model_dump() == expected_models
        assert meta.stop == expected_stop
        assert meta.prompt_hashes == {}
        run_dirs.append(run_dir)
    assert run_dirs[0] != run_dirs[1]


def test_dry_run_prompt_hashes_are_fresh(config_dir: Path) -> None:
    files = {
        "prompts/style_spec.md": "Style — 乾杯\r\n".encode("utf-8"),
        "prompts/nested/instructions.txt": b"\xff\x00\r\nraw bytes\n",
        "cards/osvald.md": b"Osvald\r\n",
        "cards/nested/temenos.md": b"Temenos\n",
    }
    for name, content in files.items():
        path = Path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    snapshots = []
    run_dirs = []
    for style_bytes in (files["prompts/style_spec.md"], b"Revised style\r\n"):
        Path("prompts/style_spec.md").write_bytes(style_bytes)
        files["prompts/style_spec.md"] = style_bytes
        result = CliRunner().invoke(app, ARGS)
        assert result.exit_code == 0, result.output
        run_dir = Path(result.output.strip())
        hashes = json.loads((run_dir / "meta.json").read_bytes())["prompt_hashes"]
        assert hashes == {
            name: hashlib.sha256(content).hexdigest()
            for name, content in files.items()
        }
        assert list(hashes) == sorted(files)
        snapshots.append(hashes)
        run_dirs.append(run_dir)

    assert run_dirs[0] != run_dirs[1]
    assert snapshots[0]["prompts/style_spec.md"] != snapshots[1]["prompts/style_spec.md"]
    assert snapshots[0]["cards/osvald.md"] == snapshots[1]["cards/osvald.md"]
    assert {name for name in files if snapshots[0][name] != snapshots[1][name]} == {
        "prompts/style_spec.md"
    }


def test_dry_run_prompt_hashes_skip_hidden_and_missing_cards(config_dir: Path) -> None:
    Path("prompts/nested").mkdir(parents=True)
    Path("prompts/.hidden").mkdir()
    content = b"Visible prompt\r\n"
    Path("prompts/style_spec.md").write_bytes(content)
    for name in ("prompts/.gitkeep", "prompts/nested/.secret", "prompts/.hidden/prompt.md"):
        Path(name).write_bytes(b"Hidden")
    assert not Path("cards").exists()

    result = CliRunner().invoke(app, ARGS)
    assert result.exit_code == 0, result.output
    meta = json.loads((Path(result.output.strip()) / "meta.json").read_bytes())
    assert "prompts/.gitkeep" not in meta["prompt_hashes"]
    assert meta["prompt_hashes"] == {
        "prompts/style_spec.md": hashlib.sha256(content).hexdigest()
    }


def test_invalid_stop_creates_no_run(config_dir: Path) -> None:
    result = CliRunner().invoke(app, ARGS + ["--stop", "fixed:0"])
    assert result.exit_code != 0
    assert not (config_dir.parent / "runs").exists()
