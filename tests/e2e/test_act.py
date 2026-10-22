import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from story_engine.agents.narrator import strip_markers
from story_engine.cli import app

WORLD_ID = os.environ.get('STORY_ENGINE_WORLD')
ACT = os.environ.get('STORY_ENGINE_ACT')
POV = os.environ.get('STORY_ENGINE_POV')


@pytest.mark.e2e
@pytest.mark.skipif(not WORLD_ID or not ACT or not POV,
                    reason='STORY_ENGINE_WORLD, STORY_ENGINE_ACT, or STORY_ENGINE_POV is not set')
def test_act(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, [
        'world', 'tell', WORLD_ID, '--day', '1', '--act', ACT, '--pov', POV,
    ])
    assert result.exit_code == 0, result.output
    run_dir = Path(result.output.strip())
    act = strip_markers((run_dir / 'acts' / 'act_1.md').read_text(encoding='utf-8'))
    assert 500 <= len(act.split()) <= 1100
