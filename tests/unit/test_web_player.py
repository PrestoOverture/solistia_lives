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
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=FIXTURES)) as client:
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
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=FIXTURES)) as client:
        response = client.get('/world/player/scene/1')
        assert response.status_code == 200
        assert embedded_beats(response.text) == [
            dict(event_id=2, text='Agnea waves.', speaker=None, actor=None, hidden=False, audio_url=None),
            dict(event_id=2, text='Hello, Mabel!', speaker='Agnea Bristarni', actor='agnea', hidden=False, audio_url='/world/player/audio/2.mp3'),
            dict(event_id=3, text='The greeting succeeds.', speaker=None, actor=None, hidden=True, audio_url=None),
            dict(event_id=4, text='Welcome!', speaker='Mabel', actor='Mabel', hidden=False, audio_url='/world/player/audio/4.mp3'),
            dict(event_id=5, text='Throné nods.', speaker=None, actor=None, hidden=False, audio_url=None),
            dict(event_id=6, text='Mabel smiles. "A whole unsplit legacy line."', speaker=None, actor=None, hidden=False, audio_url=None),
            dict(event_id=7, text='A bell rings.', speaker=None, actor=None, hidden=True, audio_url=None),
            dict(event_id=7, text='The festival begins.', speaker='world', actor='world', hidden=True, audio_url='/world/player/audio/7.mp3'),
        ]
        assert '<div class="backdrop morning">Cropdale' in response.text
        for actor in ['agnea', 'throne', 'Mabel']:
            assert f'class="figure" data-actor="{actor}"' in response.text
        assert 'id="show-world" type="checkbox">' in response.text
        assert 'id="auto" type="checkbox"> Auto' in response.text
        assert 'intent' not in response.text
        second = client.get('/world/player/scene/2')
        assert '<div class="backdrop night">Cropdale' in second.text
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
    with TestClient(create_app(runs_dir=tmp_path, worlds_dir=FIXTURES)) as client:
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
