import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from story_engine.cli import app

WORLD_ID = os.environ.get('STORY_ENGINE_WORLD')
EPISODE_RUN = os.environ.get('STORY_ENGINE_EPISODE_RUN')


@pytest.mark.e2e
@pytest.mark.skipif(not WORLD_ID or not EPISODE_RUN,
                    reason='STORY_ENGINE_WORLD or STORY_ENGINE_EPISODE_RUN is not set')
def test_narrator(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, [
        'world', 'tell', WORLD_ID, '--episode-from', EPISODE_RUN,
    ])
    assert result.exit_code == 0, result.output
    run_dir = Path(result.output.strip())
    story = (run_dir / 'story.md').read_text(encoding='utf-8')
    assert 1800 <= len(story.split()) <= 3300
