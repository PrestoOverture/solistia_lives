import json
from pathlib import Path
import random
import re

import pytest
import yaml
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.config import ConfigError, Models, load_configs
from story_engine.eval import pack as pack_module
from story_engine.runs import RunMeta, create_run, finish_run


REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def pack_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    blind_root = tmp_path / "packets"
    for directory, names in (
        ("config", ["models.yaml", "settings.yaml"]),
        ("eval", ["judge_absolute.md", "judge_pairwise.md"]),
    ):
        (repo / directory).mkdir(parents=True)
        for name in names:
            (repo / directory / name).write_bytes((REPO / directory / name).read_bytes())
    settings_path = repo / "config/settings.yaml"
    settings = yaml.safe_load(settings_path.read_text())
    settings["blind_root"] = str(blind_root)
    settings_path.write_text(yaml.safe_dump(settings))
    monkeypatch.chdir(repo)
    # Even tests of the default path must never touch the real home directory.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    models, _ = load_configs()
    runs = {}
    for mode, story in (
        ("baseline", "# Lanterns\r\nThroné watched the lanterns.\r\n"),
        ("simulation", "# The Scholar\nOsvald lifted his cup.\n"),
    ):
        run_dir = create_run(
            ["osvald", "temenos"], "new_delsta", "A quiet evening", mode,
            None, models,
        )
        (run_dir / "story.md").write_bytes(story.encode("utf-8"))
        finish_run(run_dir, "passed")
        runs[run_dir.name] = mode
    return repo, blind_root, runs


def invoke_pack(run_ids):
    result = CliRunner().invoke(app, ["eval", "pack", *run_ids])
    assert result.exit_code == 0, result.output
    paths = [Path(line) for line in result.output.splitlines()]
    return paths[:-1], paths[-1]


@pytest.mark.parametrize("missing_role", Models.model_fields)
def test_pack_historical_models(pack_workspace, missing_role):
    repo, _, runs = pack_workspace
    old_run = next(iter(runs))
    meta_path = repo / "runs" / old_run / "meta.json"
    data = json.loads(meta_path.read_bytes())
    del data["models"][missing_role]
    for role in data["models"].values():
        for field in ("base_url", "auth_token_env", "retries", "max_turns"):
            role.pop(field)
    meta_path.write_text(json.dumps(data))

    meta = RunMeta.model_validate_json(meta_path.read_bytes())
    assert set(meta.models) == set(data["models"])
    for name, role in meta.models.items():
        assert role.model == data["models"][name]["model"]
        assert role.base_url is None
        assert role.auth_token_env is None
        assert role.retries == 1
        assert role.max_turns is None
    assert RunMeta.model_validate_json(meta.model_dump_json()) == meta

    packets, key_path = invoke_pack(runs)
    assert len(packets) == 2
    key = json.loads(key_path.read_bytes())
    for packet in packets:
        assert_blind(packet, repo, runs)
        assert {source["run_id"] for source in key[packet.name].values()} == set(runs)
        for name, source in key[packet.name].items():
            assert (packet / name).read_bytes() == (
                repo / "runs" / source["run_id"] / "story.md"
            ).read_bytes()

    models_path = repo / "config/models.yaml"
    config = yaml.safe_load(models_path.read_text())
    del config[missing_role]
    models_path.write_text(yaml.safe_dump(config))
    with pytest.raises(ConfigError, match=rf"{missing_role}: Field required"):
        load_configs()


def assert_blind(packet: Path, repo: Path, run_ids):
    assert re.fullmatch(r"[0-9a-f]+", packet.name)
    assert not packet.resolve().is_relative_to(repo.resolve())
    assert not packet.resolve().is_relative_to(REPO)
    for file in packet.iterdir():
        assert file.is_file() and not file.is_symlink()
        content = file.read_text().lower()
        assert all(run_id not in content for run_id in run_ids)
        assert "baseline" not in content
        assert "simulation" not in content
        for run_id in run_ids:
            meta = json.loads((repo / "runs" / run_id / "meta.json").read_bytes())
            assert meta["created_at"].split("T")[0] not in content


def test_pairwise_five_packs(pack_workspace, monkeypatch: pytest.MonkeyPatch):
    repo, blind_root, runs = pack_workspace
    # Exercise both random orders reproducibly; five uncontrolled coin flips can all agree.
    monkeypatch.setattr(pack_module, "shuffle", random.Random(0).shuffle)
    first_orders = set()
    all_packets = set()
    all_keys = set()
    for _ in range(5):
        packets, key_path = invoke_pack(runs)
        assert len(packets) == 2
        assert key_path.parent == repo / "eval/blind"
        key = json.loads(key_path.read_bytes())
        assert set(key) == {packet.name for packet in packets}
        for packet in packets:
            assert packet.parent == blind_root
            assert {file.name for file in packet.iterdir()} == {
                "story_A.md", "story_B.md", "prompt.md",
            }
            assert (packet / "prompt.md").read_bytes() == (repo / "eval/judge_pairwise.md").read_bytes()
            assert_blind(packet, repo, runs)
            assert set(key[packet.name]) == {"story_A.md", "story_B.md"}
            assert {source["run_id"] for source in key[packet.name].values()} == set(runs)
            for name, source in key[packet.name].items():
                run_id = source["run_id"]
                assert source == {"run_id": run_id, "mode": runs[run_id]}
                assert (packet / name).read_bytes() == (repo / "runs" / run_id / "story.md").read_bytes()
        first, second = packets
        for left, right in (("story_A.md", "story_B.md"), ("story_B.md", "story_A.md")):
            assert (first / left).read_bytes() == (second / right).read_bytes()
            assert key[first.name][left] == key[second.name][right]
        first_orders.add(key[first.name]["story_A.md"]["run_id"])
        all_packets.update(packets)
        all_keys.add(key_path)
    assert len(first_orders) == 2
    assert len(all_packets) == 10
    assert len(all_keys) == 5
    assert set(blind_root.iterdir()) == all_packets
    assert set((repo / "eval/blind").iterdir()) == all_keys


def test_absolute_pack(pack_workspace):
    repo, blind_root, runs = pack_workspace
    run_id = next(iter(runs))
    packets, key_path = invoke_pack([run_id])
    assert len(packets) == 1
    packet = packets[0]
    assert packet.parent == blind_root
    assert {file.name for file in packet.iterdir()} == {"story.md", "prompt.md"}
    assert (packet / "story.md").read_bytes() == (repo / "runs" / run_id / "story.md").read_bytes()
    assert (packet / "prompt.md").read_bytes() == (repo / "eval/judge_absolute.md").read_bytes()
    assert_blind(packet, repo, runs)
    assert key_path.parent == repo / "eval/blind"
    assert json.loads(key_path.read_bytes()) == {
        packet.name: {"story.md": {"run_id": run_id, "mode": runs[run_id]}},
    }


def snapshot(root: Path):
    return {
        str(path.relative_to(root)): path.read_bytes() if path.is_file() else None
        for path in root.rglob("*")
    }


@pytest.mark.parametrize("missing_index,count", [(0, 1), (0, 2), (1, 2)])
def test_missing_story_writes_nothing(pack_workspace, missing_index, count):
    repo, blind_root, runs = pack_workspace
    run_ids = list(runs)[:count]
    (repo / "runs" / run_ids[missing_index] / "story.md").unlink()
    before = snapshot(repo.parent)
    result = CliRunner().invoke(app, ["eval", "pack", *run_ids])
    assert result.exit_code == 1
    assert "story.md" in result.output
    assert snapshot(repo.parent) == before
    assert not blind_root.exists()
    assert not (repo / "eval/blind").exists()


@pytest.mark.parametrize("destination", [".", "packets", "symlink"])
def test_rejects_destination_in_repo(pack_workspace, destination):
    repo, _, runs = pack_workspace
    if destination == "symlink":
        link = repo.parent / "alias"
        link.symlink_to(repo, target_is_directory=True)
        destination = str(link / "packets")
    settings_path = repo / "config/settings.yaml"
    settings = yaml.safe_load(settings_path.read_text())
    settings["blind_root"] = destination
    settings_path.write_text(yaml.safe_dump(settings))
    before = snapshot(repo)
    result = CliRunner().invoke(app, ["eval", "pack", *runs])
    assert result.exit_code == 1
    assert "outside the repository" in result.output
    assert snapshot(repo) == before


@pytest.mark.parametrize("configured", [True, False])
def test_expands_home_and_defaults(pack_workspace, configured):
    repo, _, runs = pack_workspace
    settings_path = repo / "config/settings.yaml"
    settings = yaml.safe_load(settings_path.read_text())
    if configured:
        settings["blind_root"] = "~/custom_packets"
    else:
        settings.pop("blind_root")
    settings_path.write_text(yaml.safe_dump(settings))
    packets, _ = invoke_pack([next(iter(runs))])
    expected = repo.parent / "home" / ("custom_packets" if configured else "blind_packets")
    assert packets[0].parent == expected


@pytest.mark.parametrize("identifier", ["run_id", "date", "baseline", "SIMULATION"])
def test_rejects_identifying_content_without_writes(pack_workspace, identifier):
    repo, _, runs = pack_workspace
    run_id = next(iter(runs))
    if identifier == "run_id":
        identifier = run_id
    elif identifier == "date":
        meta = json.loads((repo / "runs" / run_id / "meta.json").read_bytes())
        identifier = meta["created_at"].split("T")[0]
    (repo / "runs" / run_id / "story.md").write_text(identifier)
    before = snapshot(repo.parent)
    result = CliRunner().invoke(app, ["eval", "pack", *runs])
    assert result.exit_code == 1
    assert "run-identifying content" in result.output
    assert snapshot(repo.parent) == before
