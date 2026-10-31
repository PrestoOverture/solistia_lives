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


def test_scene_has_speech_bubble_and_narration_box(tmp_path):
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=FIXTURES,
                              player_assets_dir=tmp_path / 'no-art')) as client:
        response = client.get('/world/player/scene/1')
        assert response.status_code == 200
        assert 'id="speech-bubble"' in response.text
        assert 'id="narration"' in response.text


def test_scene_embeds_exact_ordered_beats_and_cast_without_writing(tmp_path):
    before = {p: p.read_bytes() for p in FIXTURES.rglob('*') if p.is_file()}
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=FIXTURES, player_assets_dir=tmp_path / "no-art")) as client:
        response = client.get('/world/player/scene/1')
        assert response.status_code == 200
        assert embedded_beats(response.text) == [
            dict(departed=[], event_id=2, text='Agnea waves.', speaker=None, actor=None, hidden=False, audio_url='/world/player/audio/2.action.mp3'),
            dict(departed=[], event_id=2, text='Hello, Mabel!', speaker='Agnea Bristarni', actor='agnea', hidden=False, audio_url='/world/player/audio/2.mp3'),
            dict(departed=[], event_id=3, text='The greeting succeeds.', speaker=None, actor=None, hidden=True, audio_url=None),
            dict(departed=[], event_id=4, text='Welcome!', speaker='Mabel', actor='Mabel', hidden=False, audio_url='/world/player/audio/4.mp3'),
            dict(departed=[], event_id=5, text='Throné nods.', speaker=None, actor=None, hidden=False, audio_url='/world/player/audio/5.action.mp3'),
            dict(departed=[], event_id=6, text='Mabel smiles. "A whole unsplit legacy line."', speaker=None, actor=None, hidden=False, audio_url=None),
            dict(departed=[], event_id=7, text='A bell rings.', speaker=None, actor=None, hidden=True, audio_url='/world/player/audio/7.action.mp3'),
            dict(departed=[], event_id=7, text='The festival begins.', speaker='world', actor='world', hidden=True, audio_url='/world/player/audio/7.mp3'),
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
        assert embedded_beats(second.text) == [dict(departed=[], event_id=8, text='Only in scene two.', speaker=None, actor=None, hidden=False, audio_url=None)]
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
    (directory / "clean/cropdale").mkdir(parents=True)
    (directory / "stages").mkdir()
    (directory / "sprites").mkdir()
    # A generated 1x1 RGBA PNG: no network or copyrighted test assets.
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00\xff")) + chunk(b"IEND", b""))
    for name in ["clean/cropdale/day.png", "sprites/agnea.png", "sprites/minor.png", "unlisted.png"]:
        (directory / name).write_bytes(png)
    (directory / "manifest.yaml").write_text(
        "stand_ins: {}\n"
        "sprites:\n  agnea: sprites/agnea.png\n  minor: sprites/minor.png\n")
    (directory / "clean/cropdale/night.png").write_bytes(png)
    (directory / "stages/cropdale.yaml").write_text(
        "default: square\nspots:\n- id: square\n  day: day.png\n  night: night.png\n"
        "  stand: [{x: 0.4, y: 0.7, h: 0.1}, {x: 0.6, y: 0.7, h: 0.1}]\n"
        "- id: bridge\n  day: night.png\n  stand: [{x: 0.5, y: 0.6, h: 0.12}]\n")
    (directory / "sprites/index.yaml").write_text(
        "sprites:\n- {file: minor.png, who: townsperson, sex: f, view: front}\n")
    return directory


def test_manifest_art_and_independent_placeholder_fallbacks(tmp_path, player_art):
    with TestClient(create_app(runs_dir=tmp_path / "runs", worlds_dir=FIXTURES,
                              player_assets_dir=player_art)) as client:
        html = client.get('/world/player/scene/1').text
        assert 'class="backdrop morning has-art"' in html
        assert 'src="http://testserver/player-assets/clean/cropdale/day.png"' in html
        for name, filename in [('agnea', 'agnea'), ('Mabel', 'minor')]:
            figure = re.search(r'<div class="figure" data-actor="' + name + r'"[^>]*>(.*?)</div>', html, re.S).group(1)
            assert f'/player-assets/sprites/{filename}.png' in figure
            assert 'class="head"' not in figure
        throne = re.search(r'<div class="figure" data-actor="throne"[^>]*>(.*?)</div>', html, re.S).group(1)
        assert 'class="head"' in throne  # Missing traveler must not use minor art.
        assert 'image-rendering: pixelated' in html
        assert "classList.toggle('speaking', speaking)" in html
        assert "classList.toggle('dimmed'" in html
        assert '--x: 40.0%; --y: 70.0%; --h: 10.0%' in html
        catalog = player_art / 'stages/cropdale.yaml'
        original = catalog.read_text()
        catalog.unlink()
        unmapped = client.get('/world/player/scene/1').text
        assert '<img class="backdrop-art' not in unmapped
        assert '/player-assets/sprites/agnea.png' in unmapped
        catalog.write_text(original)
        (player_art / 'clean/cropdale/day.png').unlink()
        (player_art / 'clean/cropdale/night.png').unlink()
        (player_art / 'sprites/minor.png').unlink()
        html = client.get('/world/player/scene/1').text
        assert 'class="backdrop morning"' in html
        assert '<img class="backdrop-art' not in html
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
        for name in ['clean/cropdale/day.png', 'sprites/agnea.png', 'sprites/minor.png']:
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


@pytest.mark.parametrize('spot,image,x', [
    ('bridge', 'night.png', .5), ('square', 'day.png', .4),
    ('free text spot', 'day.png', .4), (None, 'day.png', .4),
])
def test_catalog_spot_selection(player_art, spot, image, x):
    from story_engine.web.player import load_art, scene_stage
    stage = scene_stage(player_art, 'cropdale', spot, 'morning', load_art(player_art))
    assert stage.image == f'clean/cropdale/{image}'
    assert stage.stand[0].x == x


def test_stand_in_only_without_own_catalog(player_art):
    from story_engine.web.player import PlayerArt, scene_stage
    art = PlayerArt(stand_ins={'library': 'cropdale/bridge', 'cropdale': 'cropdale/bridge'})
    stage = scene_stage(player_art, 'library', 'square', 'morning', art)
    assert stage.image == 'clean/cropdale/night.png'
    assert stage.stand[0].x == .5
    assert scene_stage(player_art, 'cropdale', None, 'morning', art).image == 'clean/cropdale/day.png'
    assert scene_stage(player_art, 'unknown', None, 'night', art).image is None
    assert scene_stage(player_art, '../cropdale', None, 'morning', art).stand == []


@pytest.mark.parametrize('part', ['morning', 'afternoon', 'evening', 'night'])
@pytest.mark.parametrize('available', ['both', 'day', 'night'])
def test_day_night_selection_and_both_fallbacks(player_art, part, available):
    from story_engine.web.player import PlayerArt, scene_stage
    if available != 'both':
        (player_art / f'clean/cropdale/{"night" if available == "day" else "day"}.png').unlink()
    night = part in {'evening', 'night'}
    expected = ('night' if night else 'day') if available == 'both' else available
    stage = scene_stage(player_art, 'cropdale', None, part, PlayerArt())
    assert stage.image == f'clean/cropdale/{expected}.png'
    assert stage.darken == (night and available == 'day')


def test_catalog_null_image_fallbacks_and_darkening_html(tmp_path, player_art):
    from story_engine.web.player import PlayerArt, scene_stage
    catalog = player_art / 'stages/cropdale.yaml'
    text = catalog.read_text()
    catalog.write_text(text.replace('night: night.png', 'night: null'))
    stage = scene_stage(player_art, 'cropdale', None, 'evening', PlayerArt())
    assert stage.image == 'clean/cropdale/day.png' and stage.darken
    with TestClient(create_app(runs_dir=tmp_path, worlds_dir=FIXTURES,
                              player_assets_dir=player_art)) as client:
        assert '<img class="backdrop-art darkened"' in client.get('/world/player/scene/2').text
    catalog.write_text(text.replace('day: day.png', 'day: null'))
    stage = scene_stage(player_art, 'cropdale', None, 'morning', PlayerArt())
    assert stage.image == 'clean/cropdale/night.png' and not stage.darken


def test_stand_point_order_and_overflow():
    from story_engine.web.player import StandPoint, stand_points
    points = [StandPoint(x=.4, y=.7, h=.1), StandPoint(x=.6, y=.65, h=.09)]
    result = stand_points(points, 6)
    assert result[:2] == points
    assert [p.x for p in result] == pytest.approx([.4, .6, .425, .625, .45, .65])
    assert [p.y for p in result] == [.7, .65] * 3
    assert [p.h for p in result] == [.1, .09] * 3
    assert points[0].x == .4
    assert stand_points([], 4) == []


def test_departures_use_structured_moves_and_survive_hidden_beats(tmp_path):
    from story_engine.web.player import scene_beats
    directory = tmp_path / 'world'
    directory.mkdir()
    base = dict(day=1, part='morning', place='cropdale', scene='1', round=1,
                type='action', perceived_by=[])
    rows = [dict(base, id=1, actor='agnea', content='Agnea leaves. This text is not data.'),
            dict(base, id=2, actor='throne', move='leave', action='Goodbye.', say='See you.', content='Opaque.'),
            dict(base, id=3, actor='world', content='Outcome.'),
            dict(base, id=4, actor='agnea', say='Hello.', content='Opaque.')]
    (directory / 'events.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    beats = scene_beats(directory, '1', {})
    assert beats[0]['departed'] == []
    assert [b['departed'] for b in beats[1:]] == [['throne']] * 4
    assert beats[-2]['hidden']


def test_minor_sprites_use_sex_and_stable_distinct_choices(tmp_path):
    from story_engine.web.player import load_art, scene_sprites, town_sprites
    import yaml
    assets = tmp_path / 'assets'
    (assets / 'sprites').mkdir(parents=True)
    entries = []
    for sex in ('m', 'f'):
        for i in range(3):
            filename = f'{sex}{i}.png'
            (assets / 'sprites' / filename).write_bytes(b'fixture')
            entries.append({'file': filename, 'who': 'townsperson', 'sex': sex, 'view': 'front'})
    (assets / 'sprites/index.yaml').write_text(yaml.safe_dump({'sprites': entries}))
    world = tmp_path / 'world'
    world.mkdir()
    state = json.loads((FIXTURES / 'player/genesis.json').read_text())
    names = [f'Person {i}' for i in range(100)]
    state['people'] = {name: {**state['people']['Mabel'], 'sex': 'f'} for name in names}
    (world / 'state.json').write_text(json.dumps(state))
    art = load_art(assets)
    pools = town_sprites(assets)
    for name in names:
        first = scene_sprites(assets, world, [name], art)
        assert first[name] in {f'sprites/f{i}.png' for i in range(3)}
        assert first == scene_sprites(assets, world, [name], art)
    cast = names[:3]
    selected = scene_sprites(assets, world, cast, art)
    assert len(set(selected.values())) == 3
    assert selected == scene_sprites(assets, world, list(reversed(cast)), art)
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=FIXTURES,
                               player_assets_dir=assets)) as client:
        for filename in pools['m'] + pools['f']:
            assert client.get('/player-assets/' + filename).status_code == 200


def test_three_travelers_replay_field_views(tmp_path, player_art):
    from story_engine.web.player import replay_views, StandPoint, traveler_views
    import struct
    import zlib
    import yaml

    names = ['agnea', 'throne', 'temenos']
    entries = []
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    for name in names:
        for view in ['front', 'left', 'right', 'back']:
            filename = f'{name}_{view}.png'
            # Heights differ deliberately to test front-relative scaling.
            height = 40 if view == 'front' else 36
            image = (b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, height, 8, 6, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00\xff' * height))
                     + chunk(b'IEND', b''))
            (player_art / 'sprites' / filename).write_bytes(image)
            entries.append(dict(file=filename, who=name, view=view))
    (player_art / 'sprites/index.yaml').write_text(yaml.safe_dump({'sprites': entries}))
    files = traveler_views(player_art)
    assert files['agnea']['right']['scale'] == .9
    assert files['agnea']['front']['scale'] == 1
    points = [StandPoint(x=.2, y=.8, h=.1), StandPoint(x=.8, y=.8, h=.1),
              StandPoint(x=.22, y=.21, h=.1)]
    def beat(actor=None, departed=(), hidden=False):
        return dict(actor=actor, speaker=actor, departed=list(departed), hidden=hidden)
    beats = [beat(), beat('throne'), beat(), beat('agnea'), beat('agnea'),
             beat('temenos', hidden=True), beat('agnea', departed=['temenos']),
             beat('throne', departed=['temenos', 'throne'])]
    timeline = replay_views(beats, names, points)
    assert timeline == [
        dict(agnea='front', throne='front', temenos='front'),
        dict(agnea='right', throne='left', temenos='right'),
        dict(agnea='right', throne='left', temenos='right'),
        dict(agnea='right', throne='left', temenos='left'),
        dict(agnea='right', throne='left', temenos='left'),
        dict(agnea='back', throne='back', temenos='left'),
        dict(agnea='right', throne='left', temenos='left'),
        dict(agnea='right', throne='left', temenos='left'),
    ]
    # The first speaker chooses the nearest; Agnea then answers Throné,
    # although Temenos is closer. Hidden speech participates in the fold.
    with TestClient(create_app(runs_dir=tmp_path / 'runs', worlds_dir=FIXTURES,
                              player_assets_dir=player_art)) as client:
        html = client.get('/world/player/scene/1').text
        assert '/player-assets/sprites/agnea_front.png' in html
        assert '--facing' not in html and 'face-left' not in html
        for items in files.values():
            for data in items.values():
                assert client.get('/player-assets/' + data['file']).status_code == 200
        assert client.get('/player-assets/sprites/absent_right.png').status_code == 404
