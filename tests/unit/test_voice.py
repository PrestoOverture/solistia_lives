import asyncio
import hashlib
import shutil
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.kb import TRAVELERS
from story_engine.web import create_app
from story_engine.world import voice
from story_engine.world.io import read_events


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / 'tests/fixtures'


@pytest.fixture
def fixture_world():
    # All generated world artifacts stay under tests/fixtures, never real worlds/.
    with tempfile.TemporaryDirectory(dir=FIXTURES, prefix='voice-') as temporary:
        root = Path(temporary)
        world = root / 'worlds/player'
        shutil.copytree(FIXTURES / 'worlds/player', world)
        events = read_events(world)
        events[0].say = 'Outside a scene must not be voiced.'
        events[-1].say = 'Good night.'
        (world / 'events.jsonl').write_text(''.join(e.model_dump_json() + '\n' for e in events))
        (root / 'config').mkdir()
        shutil.copyfile(ROOT / 'config/voices.yaml', root / 'config/voices.yaml')
        yield root, world


@pytest.fixture
def synthesis(monkeypatch):
    calls = []

    class FakeCommunicate:
        def __init__(self, text, speaker):
            calls.append((text, speaker))

        async def save(self, filename):
            path = Path(filename)
            assert path.parent.name == 'audio'
            assert path.name.startswith('.')
            # The public file must not exist until the entire save succeeds.
            event_id = path.name.split('.')[1]
            assert not (path.parent / f'{event_id}.mp3').exists()
            path.write_bytes(b'fixture mp3')

    monkeypatch.setattr(voice.edge_tts, 'Communicate', FakeCommunicate)
    return calls


def test_voice_cli_renders_say_only_and_skips_rerun(fixture_world, synthesis, monkeypatch):
    root, world = fixture_world
    before = {p.name: p.read_bytes() for p in world.iterdir() if p.is_file()}
    voices = voice.load_voices()
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, ['world', 'voice', 'player'])
    assert result.exit_code == 0, result.output
    assert 'Rendered 4, skipped 0' in result.output
    assert synthesis == [
        ('Hello, Mabel!', voices.travelers['agnea']),
        ('Welcome!', voices.for_speaker('Mabel')),
        ('The festival begins.', voices.for_speaker('world')),
        ('Good night.', voices.travelers['throne']),
    ]
    assert {p.name for p in (world / 'audio').iterdir()} == {'2.mp3', '4.mp3', '7.mp3', '8.mp3'}
    result = CliRunner().invoke(app, ['world', 'voice', 'player'])
    assert result.exit_code == 0
    assert 'Rendered 0, skipped 4' in result.output
    assert len(synthesis) == 4
    assert before == {p.name: p.read_bytes() for p in world.iterdir() if p.is_file()}


def test_voice_scene_filter(fixture_world, synthesis, monkeypatch):
    root, world = fixture_world
    monkeypatch.chdir(root)
    result = CliRunner().invoke(app, ['world', 'voice', 'player', '--scene', '2'])
    assert result.exit_code == 0, result.output
    assert 'Rendered 1, skipped 0' in result.output
    assert [p.name for p in (world / 'audio').iterdir()] == ['8.mp3']
    assert synthesis == [('Good night.', voice.load_voices().travelers['throne'])]
    result = CliRunner().invoke(app, ['world', 'voice', 'player', '--scene', 'missing'])
    assert result.exit_code == 1
    assert 'Unknown scene' in result.output
    assert len(synthesis) == 1


def test_stable_minor_pool_and_traveler_config():
    voices = voice.load_voices()
    assert set(voices.travelers) == TRAVELERS
    assert len(set(voices.travelers.values())) == 8
    for name in ['Mabel', 'world', 'A new person', 'Thérèse']:
        expected = voices.minor[int(hashlib.sha256(name.encode()).hexdigest(), 16) % len(voices.minor)]
        assert voices.for_speaker(name) == expected
        assert voice.load_voices().for_speaker(name) == expected


def test_failed_save_leaves_no_mp3_or_temporary(fixture_world, monkeypatch):
    _, world = fixture_world

    class FailingCommunicate:
        def __init__(self, *args):
            pass

        async def save(self, filename):
            Path(filename).write_bytes(b'partial')
            raise OSError('interrupted')

    monkeypatch.setattr(voice.edge_tts, 'Communicate', FailingCommunicate)
    with pytest.raises(OSError, match='interrupted'):
        asyncio.run(voice.render_voice(world, voice.load_voices()))
    assert list((world / 'audio').iterdir()) == []


def test_audio_route_serves_read_only_and_rejects_invalid_ids(fixture_world):
    root, world = fixture_world
    audio = world / 'audio'
    audio.mkdir()
    (audio / '2.mp3').write_bytes(b'fixture mp3')
    before = {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}
    with TestClient(create_app(runs_dir=root / 'runs', worlds_dir=world.parent)) as client:
        response = client.get('/world/player/audio/2.mp3')
        assert response.status_code == 200
        assert response.content == b'fixture mp3'
        assert response.headers['content-type'] == 'audio/mpeg'
        for url in [
            '/world/player/audio/99.mp3', '/world/unknown/audio/2.mp3',
            '/world/player/audio/abc.mp3', '/world/player/audio/-2.mp3',
            '/world/player/audio/%2E%2E.mp3', '/world/player/audio/a%2Fb.mp3',
            '/world/player/audio/a%5Cb.mp3', '/world/player/audio/C%3A.mp3',
            '/world/player%2F..%2Fplayer/audio/2.mp3',
            '/world/player%5C..%5Cplayer/audio/2.mp3', '/world/%2E%2E/audio/2.mp3',
        ]:
            assert client.get(url).status_code == 404, url
        assert client.post('/world/player/audio/2.mp3').status_code == 405
    assert before == {p: p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_audio_route_rejects_symlinks(fixture_world):
    root, world = fixture_world
    audio = world / 'audio'
    audio.mkdir()
    (root / 'outside.mp3').write_bytes(b'private')
    (audio / '2.mp3').symlink_to(root / 'outside.mp3')
    with TestClient(create_app(runs_dir=root / 'runs', worlds_dir=world.parent)) as client:
        assert client.get('/world/player/audio/2.mp3').status_code == 404
        (audio / '2.mp3').unlink()
        audio.rmdir()
        audio.symlink_to(root, target_is_directory=True)
        assert client.get('/world/player/audio/2.mp3').status_code == 404
