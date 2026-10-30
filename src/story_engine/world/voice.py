"""Pre-render scene action and dialogue fields; never interpret event content."""

import asyncio
import hashlib
import os
import tempfile
from pathlib import Path

import edge_tts
import yaml
from pydantic import BaseModel, RootModel, model_validator

from story_engine.kb import TRAVELERS
from story_engine.config import load_settings
from .io import read_events, read_scenes, _atomic_write
from .models import Person, WorldState


class VoiceSelection(BaseModel):
    voice: str
    pitch: str


class AudioVoices(RootModel[dict[str, VoiceSelection]]):
    pass


class Voices(BaseModel):
    narrator: str
    travelers: dict[str, str]
    minor: dict[str, list[str]]

    @model_validator(mode="after")
    def check_pools(self):
        if set(self.minor) != {"m", "f"} or any(len(pool) < 2 for pool in self.minor.values()):
            raise ValueError("minor voices need m and f pools with at least two voices each")
        return self

    @model_validator(mode='after')
    def check_voices(self):
        if set(self.travelers) != TRAVELERS:
            raise ValueError('voices must map all eight travelers')
        if len(set(self.travelers.values())) != len(TRAVELERS):
            raise ValueError('travelers must have distinct voices')
        if self.narrator in self.travelers.values():
            raise ValueError('narrator must have a distinct voice from travelers')
        if any(not voice.startswith('en-') for voice in [self.narrator, *self.travelers.values(), *self.minor["m"], *self.minor["f"]]):
            raise ValueError('voices must be English')
        return self

    def for_speaker(self, name: str, sex: str | None = None) -> str:
        if name in self.travelers:
            return self.travelers[name]
        number = int.from_bytes(hashlib.sha256(name.encode('utf-8')).digest(), 'big')
        pool = self.minor[sex] if sex in self.minor else self.minor["m"] + self.minor["f"]
        return pool[number % len(pool)]

    def pitch_for(self, name: str) -> str:
        if name in self.travelers:
            return "+0Hz"
        number = int.from_bytes(hashlib.sha256(name.encode("utf-8")).digest(), "big")
        return f"{(number % 5 - 2) * 5:+d}Hz"


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
    people = read_people(world_dir)
    mapping_path = audio / 'voices.json'
    mapping = AudioVoices.model_validate_json(mapping_path.read_bytes()) if mapping_path.is_file() else AudioVoices({})
    counts = {'action': [0, 0], 'say': [0, 0]}
    semaphore = asyncio.Semaphore(concurrency)

    async def render_line(target: Path, text: str, speaker: str, pitch: str, kind: str, key: str):
        async with semaphore:
            descriptor, temporary = tempfile.mkstemp(dir=audio, prefix=f'.{target.stem}.', suffix='.mp3')
            os.close(descriptor)
            try:
                await edge_tts.Communicate(text, speaker, pitch=pitch).save(temporary)
                os.replace(temporary, target)
                mapping.root[key] = VoiceSelection(voice=speaker, pitch=pitch)
                _atomic_write(mapping_path, mapping.model_dump_json(indent=2) + '\n')
                counts[kind][0] += 1
            finally:
                Path(temporary).unlink(missing_ok=True)

    jobs = []
    for event in events:
        if event.scene is None or (scene is not None and event.scene != scene):
            continue
        for kind, text, speaker, suffix in (
            ('action', event.action, voices.narrator, '.action.mp3'),
            ('say', event.say, voices.for_speaker(event.actor, people[event.actor].sex if event.actor in people else None), '.mp3'),
        ):
            if not text:
                continue
            audio.mkdir(exist_ok=True)
            target = audio / f'{event.id}{suffix}'
            pitch = voices.pitch_for(event.actor) if kind == 'say' else '+0Hz'
            key = str(event.id) if kind == 'say' else f'{event.id}.action'
            if target.is_file() and mapping.root.get(key) == VoiceSelection(voice=speaker, pitch=pitch):
                counts[kind][1] += 1
                continue
            jobs.append(render_line(target, text, speaker, pitch, kind, key))
    results = await asyncio.gather(*jobs, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result
    return {kind: tuple(count) for kind, count in counts.items()}


def read_people(world_dir: Path) -> dict[str, Person]:
    """Read the persisted people projection, including backfilled sex."""
    path = world_dir / 'state.json'
    if not path.exists():
        return {}
    if path.is_symlink():
        raise ValueError('state.json must not be a symlink')
    return WorldState.model_validate_json(path.read_bytes()).people
