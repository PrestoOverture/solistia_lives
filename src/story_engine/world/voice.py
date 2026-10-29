"""Pre-render only committed scene dialogue; never interpret event content."""

import hashlib
import os
import tempfile
from pathlib import Path

import edge_tts
import yaml
from pydantic import BaseModel, Field, model_validator

from story_engine.kb import TRAVELERS
from .io import read_events, read_scenes


class Voices(BaseModel):
    travelers: dict[str, str]
    minor: list[str] = Field(min_length=2)

    @model_validator(mode='after')
    def check_voices(self):
        if set(self.travelers) != TRAVELERS:
            raise ValueError('voices must map all eight travelers')
        if len(set(self.travelers.values())) != len(TRAVELERS):
            raise ValueError('travelers must have distinct voices')
        if any(not voice.startswith('en-') for voice in [*self.travelers.values(), *self.minor]):
            raise ValueError('voices must be English')
        return self

    def for_speaker(self, name: str) -> str:
        if name in self.travelers:
            return self.travelers[name]
        number = int.from_bytes(hashlib.sha256(name.encode('utf-8')).digest(), 'big')
        return self.minor[number % len(self.minor)]


def load_voices(path: Path = Path('config/voices.yaml')) -> Voices:
    return Voices.model_validate(yaml.safe_load(path.read_text(encoding='utf-8')))


async def render_voice(world_dir: Path, voices: Voices, scene: str | None = None) -> tuple[int, int]:
    if scene is not None and scene not in {item.id for item in read_scenes(world_dir)}:
        raise ValueError(f'Unknown scene: {scene}')
    events = read_events(world_dir)
    audio = world_dir / 'audio'
    if audio.is_symlink():
        raise ValueError('audio directory must not be a symlink')
    rendered = skipped = 0
    for event in events:
        if event.scene is None or not event.say or (scene is not None and event.scene != scene):
            continue
        audio.mkdir(exist_ok=True)
        target = audio / f'{event.id}.mp3'
        if target.is_file():
            skipped += 1
            continue
        descriptor, temporary = tempfile.mkstemp(dir=audio, prefix=f'.{event.id}.', suffix='.mp3')
        os.close(descriptor)
        try:
            await edge_tts.Communicate(event.say, voices.for_speaker(event.actor)).save(temporary)
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        rendered += 1
    return rendered, skipped
