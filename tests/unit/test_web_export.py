import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.web import create_app
from story_engine.web.export import NOTICE, export_site

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / 'tests/fixtures/worlds'
spec = importlib.util.spec_from_file_location('check_site', ROOT / 'scripts/check_site.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


@pytest.fixture
def exported(tmp_path):
    assets = tmp_path / 'art'
    (assets / 'sprites').mkdir(parents=True)
    (assets / 'sprites/used.png').write_bytes(b'original fixture art')
    (assets / 'sprites/unused.png').write_bytes(b'not referenced')
    (assets / 'manifest.yaml').write_text('sprites:\n  agnea: sprites/used.png\n')
    worlds = tmp_path / 'worlds'
    shutil.copytree(FIXTURES / 'player', worlds / 'player')
    (worlds / 'player/audio-public').mkdir()
    # The fixture has both action and spoken beats; copy just one selected recording.
    (worlds / 'player/audio-public/2.mp3').write_bytes(b'public voice')
    (worlds / 'player/audio').mkdir(exist_ok=True)
    (worlds / 'player/audio/4.mp3').write_bytes(b'private voice')
    out = tmp_path / 'site'
    export_site(['player'], assets=assets, audio='audio-public', out=out, worlds_dir=worlds)
    return out, assets, worlds


def test_export_index_theater_assets_audio_and_links(exported):
    out, assets, worlds = exported
    index = (out / 'index.html').read_text()
    assert NOTICE in index
    assert 'Agnea Bristarni' in index and 'Throné Anguis' in index
    assert 'Cropdale' in index and '1 day' in index and '1 days' not in index
    assert 'world/player/theater.html' in index
    assert 'world/player/chronicle.html' in index
    chronicle = (out / 'world/player/chronicle.html').read_text()
    assert 'href="../../index.html"' in chronicle and 'cdn.jsdelivr' not in chronicle
    assert 'href="/world/' not in chronicle
    assert 'href="theater.html#' in chronicle
    html = (out / 'world/player/theater.html').read_text()
    assert 'id="title-card"' in html and 'cdn.jsdelivr' not in html
    data = json.loads((out / 'world/player/theater.json').read_text())
    beats = [beat for scene in data['scenes'] for beat in scene['beats']]
    assert any(beat['audio_url'] == 'audio/2.mp3' for beat in beats)
    assert any(beat['audio_url'] is None and beat['speaker'] for beat in beats)
    assert (out / 'world/player/audio/2.mp3').read_bytes() == b'public voice'
    assert not (out / 'world/player/audio/4.mp3').exists()
    assert (out / 'assets/sprites/used.png').read_bytes() == b'original fixture art'
    assert not (out / 'assets/sprites/unused.png').exists()
    assert checker.check_site(out) == []
    with TestClient(create_app(worlds_dir=worlds, player_assets_dir=assets)) as client:
        live = client.get('/world/player/theater.json').json()
    assert data['scenes'][0]['view_timeline'] == live['scenes'][0]['view_timeline']
    assert data['scenes'][0]['beats'][0]['text'] == live['scenes'][0]['beats'][0]['text']


@pytest.mark.parametrize('url', ['missing.png', '/world/player/audio/2.mp3',
                                      '/player-assets/sprites/used.png', '../../../outside.png'])
@pytest.mark.parametrize('embedded', [False, True])
def test_checker_rejects_dangling_and_absolute_urls(exported, url, embedded):
    out, _, _ = exported
    path = out / 'world/player/theater.html'
    if embedded:
        path.write_text(path.read_text() + '<script type="application/json">' +
                        json.dumps({'audio_url': url}) + '</script>')
    else:
        path.write_text(path.read_text() + f'<img src="{url}">')
    assert checker.check_site(out)


def test_web_assets_cli_honored(monkeypatch, tmp_path):
    import uvicorn
    captured = []
    monkeypatch.setattr(uvicorn, 'run', lambda app, **kw: captured.append(app))
    assets = tmp_path / 'art'
    assets.mkdir()
    (assets / 'manifest.yaml').write_text('sprites:\n  agnea: agnea.png\n')
    (assets / 'agnea.png').write_bytes(b'custom art')
    assert CliRunner().invoke(app, ['web', '--assets', str(assets)]).exit_code == 0
    with TestClient(captured[0]) as client:
        assert client.get('/player-assets/agnea.png').content == b'custom art'


def test_export_cli_assets_honored(exported, monkeypatch, tmp_path):
    _, assets, worlds = exported
    monkeypatch.chdir(tmp_path)
    # Display metadata comes from the checkout KB; absent locations safely use slugs.
    shutil.copytree(ROOT / 'kb/characters', tmp_path / 'kb/characters')
    shutil.copytree(ROOT / 'config', tmp_path / 'config')
    result = CliRunner().invoke(app, ['world', 'export', 'player', '--assets', str(assets),
                                      '--audio', 'audio-public', '--out', str(tmp_path / 'cli-site')])
    assert result.exit_code == 0, result.output
    assert (tmp_path / 'cli-site/assets/sprites/used.png').read_bytes() == b'original fixture art'


def test_checker_checks_external_theater_json(exported):
    out, _, _ = exported
    path = out / 'world/player/theater.json'
    data = json.loads(path.read_text())
    data['scenes'][0]['backdrop'] = 'dangling.jpg'
    path.write_text(json.dumps(data))
    assert any('theater.json: missing file dangling.jpg' in error for error in checker.check_site(out))
