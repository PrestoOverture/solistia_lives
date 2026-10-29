"""Pre-render scene action and dialogue fields; never interpret event content."""

import asyncio
import hashlib
import os
import tempfile
from pathlib import Path

import edge_tts
import yaml
from pydantic import BaseModel, Field, model_validator

from story_engine.kb import TRAVELERS
from story_engine.config import load_settings
from .io import read_events, read_scenes


class Voices(BaseModel):
    narrator: str
    travelers: dict[str, str]
    minor: list[str] = Field(min_length=2)

    @model_validator(mode='after')
    def check_voices(self):
        if set(self.travelers) != TRAVELERS:
            raise ValueError('voices must map all eight travelers')
        if len(set(self.travelers.values())) != len(TRAVELERS):
            raise ValueError('travelers must have distinct voices')
        if self.narrator in self.travelers.values():
            raise ValueError('narrator must have a distinct voice from travelers')
        if any(not voice.startswith('en-') for voice in [self.narrator, *self.travelers.values(), *self.minor]):
            raise ValueError('voices must be English')
        return self

    def for_speaker(self, name: str) -> str:
        if name in self.travelers:
            return self.travelers[name]
        number = int.from_bytes(hashlib.sha256(name.encode('utf-8')).digest(), 'big')
        return self.minor[number % len(self.minor)]


def load_voices(path: Path = Path('config/voices.yaml')) -> Voices:
    return Voices.model_validate(yaml.safe_load(path.read_text(encoding='utf-8')))


async def render_voice(
    world_dir: Path, voices: Voices, scene: str | None = None, *,
    concurrency: int | None = None,
) -> dict[str, tuple[int, int]]:
    if concurrency is None:
        concurrency = load_settings().voice_concurrency
    if concurrency < 1:
        raise ValueError('voice concurrency must be positive')
    if scene is not None and scene not in {item.id for item in read_scenes(world_dir)}:
        raise ValueError(f'Unknown scene: {scene}')
    events = read_events(world_dir)
    audio = world_dir / 'audio'
    if audio.is_symlink():
        raise ValueError('audio directory must not be a symlink')
    counts = {'action': [0, 0], 'say': [0, 0]}
    semaphore = asyncio.Semaphore(concurrency)

    async def render_line(target: Path, text: str, speaker: str, kind: str):
        async with semaphore:
            descriptor, temporary = tempfile.mkstemp(dir=audio, prefix=f'.{target.stem}.', suffix='.mp3')
            os.close(descriptor)
            try:
                await edge_tts.Communicate(text, speaker).save(temporary)
                os.replace(temporary, target)
                counts[kind][0] += 1
            finally:
                Path(temporary).unlink(missing_ok=True)

    jobs = []
    for event in events:
        if event.scene is None or (scene is not None and event.scene != scene):
            continue
        for kind, text, speaker, suffix in (
            ('action', event.action, voices.narrator, '.action.mp3'),
            ('say', event.say, voices.for_speaker(event.actor), '.mp3'),
        ):
            if not text:
                continue
            audio.mkdir(exist_ok=True)
            target = audio / f'{event.id}{suffix}'
            if target.is_file():
                counts[kind][1] += 1
                continue
            jobs.append(render_line(target, text, speaker, kind))
    results = await asyncio.gather(*jobs, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return {kind: tuple(count) for kind, count in counts.items()}
