"""A setting survives world creation, a separate day run and a chronicle request."""

import hashlib
import json
from pathlib import Path

import pytest
import yaml
from claude_agent_sdk import ResultMessage
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from story_engine.agents import character, initializer, world
from story_engine.cli import app
from story_engine.kb import validate_input
from story_engine.setting import render_prompt
from story_engine.web import create_app
from story_engine.world.io import load_state, read_scenes

ROOT = Path(__file__).resolve().parents[2]
SETTING = ROOT / "tests/fixtures/settings/bell"
GOALS = {"mara": "Ring the bell", "ivo": "Record the tide"}


@pytest.mark.parametrize("filename,digest", [
    ("world.md", "50c618754240ec163aa40fd59f5332fdd748cdddcb2245c4224efab7b617f547"),
    ("world_offscreen.md", "43ffbdf387bfda9221eb4245df7d7fa703aa26a1742321856cb58a155e228290"),
    ("character.md", "3015e01614cce0fc30848f309c441e7d41a7b65b6d2625ee4038611043fa9f70"),
    ("initializer_scene_context.md", "59827d553f1bf986016364f368597311e677528c0a0e4a52b98489499152eccf"),
])
def test_default_prompt_matches_original_bytes(filename, digest):
    assert hashlib.sha256(render_prompt(ROOT, filename).encode()).hexdigest() == digest


@pytest.mark.parametrize("ending", ["", "The tide always turns."])
def test_setting_prompt_ending(tmp_path, ending):
    premise = yaml.safe_load((SETTING / "premise.yaml").read_text())
    assert "ending" not in premise
    if ending:
        premise["ending"] = ending
    (tmp_path / "premise.yaml").write_text(yaml.safe_dump(premise))
    template = (ROOT / "prompts/world_offscreen.md").read_text()
    expected = template.replace("{{premise}}", premise["world_offscreen"])
    assert render_prompt(ROOT, "world_offscreen.md", tmp_path) == expected.replace(
        "{{ending}}", " " + ending if ending else ""
    )


def starting_state(spot):
    return {
        "places": [{"slug": "bellport", "details": []}],
        "characters": {slug: dict(where="bellport", spot=spot, goals=[GOALS[slug]], commitments=[])
                       for slug in ("mara", "ivo")},
        "people": {"Keeper": dict(kb="keeper", sex="m", where="bellport", spot="bell_rail",
                                  wants=["Wait for low tide"], commitments=[])},
        "situations": [dict(id="tide", kind="trouble", summary="The tide is rising", touches=["mara"],
                            people=["Keeper"], opposed_by=["Keeper"], at_stake={"mara": GOALS["mara"]},
                            heard="The bell is silent.", status="open", next="The tide turns.",
                            due=dict(day=2, part="morning"))],
    }


def test_world_uses_its_recorded_setting(tmp_path, monkeypatch):
    for folder in ("config", "prompts", "kb", "cards", "assets"):
        (tmp_path / folder).symlink_to(ROOT / folder, target_is_directory=True)
    (tmp_path / "bell").symlink_to(SETTING, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    premise = yaml.safe_load((SETTING / "premise.yaml").read_text())
    cards = {path.stem: path.read_text().strip() for path in (SETTING / "cards").glob("*.md")}
    calls = []

    class FakeClient:
        def __init__(self, *, options):
            self.options = options

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, prompt):
            self.request = prompt
            calls.append((self.options.system_prompt, prompt))

        async def receive_response(self):
            system = self.options.system_prompt
            assert "Solistia" not in system
            assert self.options.cwd == SETTING
            pre = self.options.hooks["PreToolUse"][0].hooks[0]
            for kb, decision in ((SETTING / "kb", "allow"), (ROOT / "kb", "deny")):
                inputs = dict(tool_name="Glob", tool_input=dict(path=str(kb), pattern="**/*.md"))
                assert (await pre(inputs, None, {}))["hookSpecificOutput"]["permissionDecision"] == decision

            if self.request.startswith("State validation failed:"):
                assert "village_square" in self.request and "catalog" in self.request
                reply = starting_state("bell_rail")
            elif self.request.startswith("World validation failed:"):
                assert "Old Reed" in self.request and "keeper" in self.request
                reply = dict(call="adjudicate", encounters=[])
            else:
                request = json.loads(self.request)
                call = request.get("call")
                if call is None:
                    assert request["kb_path"] == str(SETTING / "kb")
                    if "scenario" in request:
                        # The scene context is shared by every main: it is built from the KB, never the private cards.
                        assert not any(card in system for card in cards.values())
                        reply = "## Location\nThe bell stands at the landing."
                    else:
                        assert all(card in system for card in cards.values())
                        assert set(request["spots"]) == {"bellport"}
                        reply = starting_state("village_square")
                elif call == "part_of_day":
                    if "goals" in request:
                        for slug, goal in GOALS.items():
                            assert (cards[slug] in system) == (request["goals"] == [goal])
                    assert request["places"] == [dict(slug="bellport", details=[], region="coast")]
                    assert request["present"]["ivo"] == "Ivo Pike"
                    reply = dict(call="plan", kind="go", where="bellport", spot="bell_rail",
                                 intent="Hear the tide", aim="Stand by the bell")
                elif call == "adjudicate":
                    reply = dict(call=call, encounters=[], ops=[])
                    if "state" in request:
                        assert request["spots"]["bellport"][0]["id"] == "bell_rail"
                        # A fixture KB alias cannot be introduced as an invented person.
                        reply["ops"].append(dict(op="introduce", name="Old Reed", sex="m",
                                                 where="bellport", wants=["Hear the tide"]))
                elif call == "scene_round":
                    reply = dict(call=call, ops=[], minor_moves={})
                elif call == "scene_move":
                    reply = dict(call="action", intent="Listen", move="leave", urge=0, action="", say="")
                elif call == "offscreen":
                    assert {main["name"] for main in request["mains"]} == {"Mara Vale", "Ivo Pike"}
                    reply = dict(call=call, events=[], situation_notes={"tide": "Still rising."})
                else:
                    assert call == "end_of_day"
                    reply = dict(call=call, summary="I heard the bell.")
            yield ResultMessage("success", 1, 1, False, 1, "fake",
                                result=reply if isinstance(reply, str) else json.dumps(reply))

    for module in (initializer, character, world):
        monkeypatch.setattr(module, "ClaudeSDKClient", FakeClient)
    runner = CliRunner()
    created = runner.invoke(app, ["world", "new", "--setting", "bell", "--characters", "mara,ivo",
                                  "--location", "bellport", "--situation", "A high tide"])
    assert created.exit_code == 0, created.output
    directory = Path(created.output.strip())
    info = json.loads((directory / "world.json").read_text())
    assert info["setting"] == str(SETTING)
    with pytest.raises(ValueError, match="unknown traveler 'osvald'"):
        validate_input("mara,osvald", "bellport", SETTING)
    with pytest.raises(ValueError, match="unknown location"):
        validate_input("mara,ivo", "cropdale", SETTING)

    simulated = runner.invoke(app, ["world", "run", directory.name, "--stop-after", "day"])
    assert simulated.exit_code == 0, simulated.output
    for prompt in ("world", "world_offscreen", "character", "initializer_scene_context", "initializer_state"):
        heading = (ROOT / "prompts" / f"{prompt}.md").read_text().splitlines()[0]
        systems = {system for system, _ in calls if system.splitlines()[0] == heading}
        assert systems, prompt
        key = "initializer_scene_context" if prompt == "initializer_state" else prompt
        for system in systems:
            assert premise[key] in system
            assert all(text not in system for other, text in premise.items() if other != key)
    assert load_state(directory).clock.day == 2
    assert all(main.spot == "bell_rail" for main in load_state(directory).characters.values())
    assert any(request.startswith("State validation failed:") for _, request in calls)
    assert any(request.startswith("World validation failed:") for _, request in calls)
    assert {scene.part for scene in read_scenes(directory)} == {"morning", "afternoon", "evening", "night"}
    for run in (Path("runs") / info["init_run_id"], Path(simulated.output.strip())):
        hashes = json.loads((run / "meta.json").read_text())["prompt_hashes"]
        assert {key for key in hashes if key.startswith("cards/")} == {"cards/mara.md", "cards/ivo.md"}
        assert "prompts/default_premise.yaml" not in hashes
        for key in ("cards/mara.md", "cards/ivo.md", "premise.yaml"):
            assert hashes[key] == hashlib.sha256((SETTING / key).read_bytes()).hexdigest()
        assert hashes["prompts/world.md"] == hashlib.sha256((ROOT / "prompts/world.md").read_bytes()).hexdigest()

    with TestClient(create_app()) as client:
        page = client.get(f"/world/{directory.name}/chronicle")
        assert page.status_code == 200
        assert "Mara Vale, Ivo Pike · Port of Bells" in page.text and "The Bronze Rail" in page.text
        data = client.get(f"/world/{directory.name}/chronicle.json")
        assert data.status_code == 200
        scene = data.json()["unthreaded"][0]
        assert scene["place_name"] == "Port of Bells" and "Mara Vale" in scene["participants"]
