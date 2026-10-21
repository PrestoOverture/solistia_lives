import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from story_engine.agents.curator import Episode, validate_episode
from story_engine.cli import app
from story_engine.world.io import read_scenes
from story_engine.world.models import WorldInfo

WORLD_ID = os.environ.get('STORY_ENGINE_WORLD')


@pytest.mark.e2e
@pytest.mark.skipif(not WORLD_ID, reason='STORY_ENGINE_WORLD is not set')
def test_curator(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    world = root / 'worlds' / WORLD_ID
    result = CliRunner().invoke(app, ['world', 'tell', WORLD_ID, '--stop-after', 'curate'])
    assert result.exit_code == 0, result.output
    episode = Episode.model_validate_json((Path(result.output.strip()) / 'episode.json').read_bytes())
    scenes = read_scenes(world)
    info = WorldInfo.model_validate_json((world / 'world.json').read_bytes())
    validate_episode(episode, scenes, info.characters)
    by_id = {scene.id: scene for scene in scenes}
    assert all(scene_id in by_id for scene_id in episode.scenes)
    chosen = [by_id[scene_id] for scene_id in episode.scenes]
    assert episode.pov in info.characters
    assert any(episode.pov in scene.participants for scene in chosen)
