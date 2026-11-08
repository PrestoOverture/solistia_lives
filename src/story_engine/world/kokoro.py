"""Local CPU synthesis, with a reusable session and a one-time model download."""

import asyncio
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from urllib.request import urlopen


MODEL_DIRECTORY = Path('models/kokoro')
MODEL_SOURCE = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0'


def model_file(name: str) -> Path:
    target = MODEL_DIRECTORY / name
    if target.is_file():
        return target
    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=MODEL_DIRECTORY, prefix=f'.{name}.')
    try:
        with os.fdopen(descriptor, 'wb') as output, urlopen(f'{MODEL_SOURCE}/{name}', timeout=60) as response:
            shutil.copyfileobj(response, output)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return target


class KokoroSynthesizer:
    def __init__(self):
        self._kokoro = None
        # Share one CPU session; phonemizer state is not safe for parallel calls.
        self._lock = asyncio.Lock()

    async def save(self, text: str, speaker: str, target: Path) -> None:
        async with self._lock:
            await asyncio.to_thread(self._save, text, speaker, target)

    def _save(self, text: str, speaker: str, target: Path) -> None:
        if shutil.which('ffmpeg') is None:
            raise RuntimeError('Kokoro MP3 rendering requires ffmpeg on PATH')
        if self._kokoro is None:
            from kokoro_onnx import Kokoro
            import onnxruntime

            model = model_file('kokoro-v1.0.onnx')
            voices = model_file('voices-v1.0.bin')
            session = onnxruntime.InferenceSession(str(model), providers=['CPUExecutionProvider'])
            self._kokoro = Kokoro.from_session(session, str(voices))
        samples, rate = self._kokoro.create(
            text, voice=speaker, lang='en-gb' if speaker.startswith('b') else 'en-us',
        )
        if samples.size == 0:
            raise RuntimeError(f'Kokoro returned no audio for {target.name}')
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
             '-f', 'f32le', '-ar', str(rate), '-ac', '1', '-i', 'pipe:0',
             '-c:a', 'libmp3lame', str(target)],
            input=samples.astype('<f4').tobytes(), capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(f'Kokoro MP3 encoding failed: {result.stderr.decode(errors="replace")}')
