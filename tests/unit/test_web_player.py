import json
import re
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from story_engine.web import create_app


FIXTURES = Path(__file__).parents[1] / 'fixtures' / 'worlds'


def embedded_beats(html):
    return json.loads(re.search(r'<script id="beats" type="application/json">(.*?)</script>',
                               html, re.S).group(1))


def test_worlds_lists_we_fixture_and_scenes(tmp_path):
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=FIXTURES, player_assets_dir=tmp_path / "no-art")) as client:
        response = client.get('/worlds')
        assert response.status_code == 200
        html = response.text
        assert 'Agnea Bristarni, Throné Anguis' in html
        assert 'Cropdale' in html
        for sid, part, rounds in [('1', 'morning', 3), ('2', 'night', 1)]:
            assert f'/world/player/scene/{sid}' in html
            assert f'Day 1 · {part} · Cropdale' in html
            assert f'{rounds} rounds' in html
        assert 'Agnea Bristarni, Throné Anguis, Mabel' in html
        # The existing fixture has genesis but no recorded scenes.
        assert 'agnea_throne' not in html
        assert 'http://testserver/worlds' in client.get('/').text


def test_scene_embeds_exact_ordered_beats_and_cast_without_writing(tmp_path):
    before = {p: p.read_bytes() for p in FIXTURES.rglob('*') if p.is_file()}
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=FIXTURES, player_assets_dir=tmp_path / "no-art")) as client:
        response = client.get('/world/player/scene/1')
        assert response.status_code == 200
        assert embedded_beats(response.text) == [
            dict(event_id=2, text='Agnea waves.', speaker=None, actor=None, hidden=False, audio_url='/world/player/audio/2.action.mp3'),
            dict(event_id=2, text='Hello, Mabel!', speaker='Agnea Bristarni', actor='agnea', hidden=False, audio_url='/world/player/audio/2.mp3'),
            dict(event_id=3, text='The greeting succeeds.', speaker=None, actor=None, hidden=True, audio_url=None),
            dict(event_id=4, text='Welcome!', speaker='Mabel', actor='Mabel', hidden=False, audio_url='/world/player/audio/4.mp3'),
            dict(event_id=5, text='Throné nods.', speaker=None, actor=None, hidden=False, audio_url='/world/player/audio/5.action.mp3'),
            dict(event_id=6, text='Mabel smiles. "A whole unsplit legacy line."', speaker=None, actor=None, hidden=False, audio_url=None),
            dict(event_id=7, text='A bell rings.', speaker=None, actor=None, hidden=True, audio_url='/world/player/audio/7.action.mp3'),
            dict(event_id=7, text='The festival begins.', speaker='world', actor='world', hidden=True, audio_url='/world/player/audio/7.mp3'),
        ]
        assert '<div class="backdrop morning">' in response.text
        assert "Cropdale" in response.text
        for actor in ['agnea', 'throne', 'Mabel']:
            assert f'class="figure" data-actor="{actor}"' in response.text
        assert 'id="show-world" type="checkbox">' in response.text
        assert 'id="auto" type="checkbox"> Auto' in response.text
        assert 'intent' not in response.text
        second = client.get('/world/player/scene/2')
        assert '<div class="backdrop night">' in second.text
        assert embedded_beats(second.text) == [dict(event_id=8, text='Only in scene two.', speaker=None, actor=None, hidden=False, audio_url=None)]
        assert client.post('/world/player/scene/1').status_code == 405
    assert before == {p: p.read_bytes() for p in FIXTURES.rglob('*') if p.is_file()}
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('url', [
    '/world/unknown/scene/1', '/world/player/scene/unknown',
    '/world/agnea_throne/scene/1',
    '/world/%2E%2E/scene/1', '/world/player/scene/%2E%2E',
    '/world/player%2F..%2Fplayer/scene/1', '/world/player/scene/a%2Fb',
    '/world/player%5C..%5Cplayer/scene/1', '/world/player/scene/a%5Cb',
    '/world/player/scene/C%3A', '/world/C%3A/scene/1',
])
def test_unknown_and_path_like_ids_are_404(tmp_path, url):
    with TestClient(create_app(runs_dir=tmp_path, worlds_dir=FIXTURES, player_assets_dir=tmp_path / "no-art")) as client:
        assert client.get(url).status_code == 404


def test_worlds_excludes_legacy_and_external_symlinks(tmp_path):
    worlds = tmp_path / 'worlds'
    worlds.mkdir()
    shutil.copytree(FIXTURES / 'player', worlds / 'legacy')
    (worlds / 'legacy' / 'genesis.json').unlink()
    (worlds / 'linked').symlink_to((FIXTURES / 'player').resolve(), target_is_directory=True)
    shutil.copytree(FIXTURES / 'player', worlds / 'file-link')
    events = worlds / 'file-link' / 'events.jsonl'
    events.unlink()
    events.symlink_to((FIXTURES / 'player' / 'events.jsonl').resolve())
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=worlds)) as client:
        assert 'No simulated worlds yet.' in client.get('/worlds').text
        for name in ['legacy', 'linked', 'file-link']:
            assert client.get(f'/world/{name}/scene/1').status_code == 404


def test_empty_worlds_does_not_create_directory(tmp_path):
    worlds = tmp_path / 'missing'
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=worlds)) as client:
        assert 'No simulated worlds yet.' in client.get('/worlds').text
    assert not worlds.exists()


@pytest.fixture
def player_art(tmp_path):
    import struct
    import zlib

    directory = tmp_path / "assets" / "player"
    (directory / "backdrops").mkdir(parents=True)
    (directory / "sprites").mkdir()
    # A generated 1x1 RGBA PNG: no network or copyrighted test assets.
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff")) + chunk(b"IEND", b""))
    for name in ["backdrops/cropdale.png", "sprites/agnea.png", "sprites/minor.png", "unlisted.png"]:
        (directory / name).write_bytes(png)
    (directory / "manifest.yaml").write_text(
        "backdrops:\n  cropdale: backdrops/cropdale.png\n"
        "sprites:\n  agnea: sprites/agnea.png\n  minor: sprites/minor.png\n")
    return directory


def test_manifest_art_and_independent_placeholder_fallbacks(tmp_path, player_art):
    with TestClient(create_app(runs_dir=tmp_path / "runs", worlds_dir=FIXTURES,
                              player_assets_dir=player_art)) as client:
        html = client.get('/world/player/scene/1').text
        assert 'class="backdrop morning has-art"' in html
        assert 'src="http://testserver/player-assets/backdrops/cropdale.png"' in html
        for name, filename in [('agnea', 'agnea'), ('Mabel', 'minor')]:
            figure = re.search(r'data-actor="' + name + r'">(.*?)</div>', html, re.S).group(1)
            assert f'/player-assets/sprites/{filename}.png' in figure
            assert 'class="head"' not in figure
        throne = re.search(r'data-actor="throne">(.*?)</div>', html, re.S).group(1)
        assert 'class="head"' in throne  # Missing traveler must not use minor art.
        assert 'image-rendering: pixelated' in html
        assert "classList.toggle('speaking', speaking)" in html
        assert "classList.toggle('dimmed'" in html
        manifest = player_art / 'manifest.yaml'
        original = manifest.read_text()
        manifest.write_text(original.replace('cropdale:', 'unmapped_place:'))
        unmapped = client.get('/world/player/scene/1').text
        assert 'class="backdrop-art"' not in unmapped
        assert '/player-assets/sprites/agnea.png' in unmapped
        manifest.write_text(original)
        (player_art / 'backdrops/cropdale.png').unlink()
        (player_art / 'sprites/minor.png').unlink()
        html = client.get('/world/player/scene/1').text
        assert 'class="backdrop morning"' in html
        assert 'class="backdrop-art"' not in html
        assert '/player-assets/sprites/agnea.png' in html
        assert '/player-assets/sprites/minor.png' not in html
        (player_art / 'manifest.yaml').unlink()
        html = client.get('/world/player/scene/1').text
        assert html.count('class="head"') == 3
        assert 'class="backdrop-art"' not in html


def test_asset_route_is_read_only_and_confined_to_manifest_images(tmp_path, player_art):
    outside = tmp_path / 'private.png'
    outside.write_bytes((player_art / 'sprites/agnea.png').read_bytes())
    (player_art / 'escape.png').symlink_to(outside)
    (player_art / 'linked').symlink_to(tmp_path, target_is_directory=True)
    with (player_art / 'manifest.yaml').open('a') as stream:
        stream.write('  escape: escape.png\n  traversal: ../../private.png\n'
                     '  absolute: ' + str(outside) + '\n  linked: linked/private.png\n'
                     '  metadata: manifest.yaml\n  missing: sprites/missing.png\n')
    before = {p: p.read_bytes() for p in player_art.rglob('*') if p.is_file()}
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=FIXTURES,
                              player_assets_dir=player_art)) as client:
        for name in ['backdrops/cropdale.png', 'sprites/agnea.png', 'sprites/minor.png']:
            response = client.get('/player-assets/' + name)
            assert response.status_code == 200
            assert response.headers['content-type'] == 'image/png'
            assert response.content == (player_art / name).read_bytes()
        for name in ['unlisted.png', 'manifest.yaml', 'SOURCES.md', 'escape.png',
                     'linked/private.png', '%2E%2E/%2E%2E/private.png',
                     '%2F' + str(outside).lstrip('/'), '..%5C..%5Cprivate.png',
                     'sprites/missing.png', 'sprites']:
            assert client.get('/player-assets/' + name).status_code == 404
        for method in ['post', 'put', 'delete', 'patch']:
            assert getattr(client, method)('/player-assets/sprites/agnea.png').status_code == 405
    assert before == {p: p.read_bytes() for p in player_art.rglob('*') if p.is_file()}
