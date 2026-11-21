"""Static export of the shared world theater."""

import json
import shutil
from pathlib import Path
from urllib.parse import quote

from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from story_engine.kb import TRAVELERS
from story_engine.web import _display_name
from story_engine.web.chronicle import chronicle_page
from story_engine.web.player import asset_file, display_name, read_world, theater_context, theater_data, valid_id


NOTICE = ('Unofficial fan project, not affiliated with or endorsed by Square Enix. '
          'Octopath Traveler is a trademark of Square Enix. '
          'All art and voices on this site are original.')


class ExportManifest(BaseModel):
    asset_root: str
    assets: list[str]


def export_site(world_ids: list[str], *, assets: Path, audio: str, out: Path,
                worlds_dir: Path = Path('worlds')) -> None:
    assets, worlds_dir, out = assets.resolve(), worlds_dir.resolve(), out.resolve()
    if not valid_id(audio):
        raise ValueError('--audio must be a directory name inside each world')
    if not assets.is_dir():
        raise ValueError(f'Asset root not found: {assets}')
    if out.exists() and any(out.iterdir()):
        raise ValueError('--out must be an empty or new directory')
    travelers = {slug: _display_name(Path('kb/characters') / slug / f'{slug}.md')
                 for slug in sorted(TRAVELERS)}
    locations = {path.stem: _display_name(path) for path in Path('kb/locations').rglob('*.md')}
    templates = Jinja2Templates(directory=Path(__file__).parent / 'templates')
    templates.env.globals['person'] = lambda slug: display_name(slug, travelers)
    worlds, referenced = [], set()
    # Prepare all worlds before writing, so invalid input cannot leave a partial site.
    for world_id in dict.fromkeys(world_ids):
        world = read_world(worlds_dir, world_id)
        if world is None:
            raise ValueError(f'World not found: {world_id}')
        audio_dir = worlds_dir / world_id / audio
        if not audio_dir.resolve().is_relative_to(worlds_dir / world_id):
            raise ValueError(f'Audio directory escapes world: {world_id}')
        scenes = theater_data(worlds_dir, world_id, assets, travelers, locations,
                              asset_prefix='../../assets/', audio_dir=audio_dir)
        for scene in scenes:
            files = [scene['backdrop'], *scene['sprite_files'].values(),
                     *(item['file'] for views in scene['sprite_views'].values() for item in views.values())]
            for url in filter(None, files):
                filename = url.removeprefix('../../assets/')
                if asset_file(assets, filename) is None:
                    raise ValueError(f'Asset not found: {filename}')
                referenced.add(filename)
            for beat in scene['beats']:
                if beat['audio_url']:
                    source = audio_dir / beat['audio_url'].removeprefix('audio/')
                    if not source.resolve().is_relative_to(audio_dir.resolve()):
                        raise ValueError(f'Audio file escapes directory: {source}')
        chronicle = chronicle_page(worlds_dir, world_id, assets, travelers, locations,
                                   theater_url='theater.html')
        worlds.append((world_id, world[0], scenes, audio_dir, chronicle))
    out.mkdir(parents=True, exist_ok=True)
    for filename in sorted(referenced):
        target = out / 'assets' / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(asset_file(assets, filename), target)
    (out / 'favicon.svg').write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        '<rect width="32" height="32" rx="6" fill="#29251f"/>'
        '<text x="16" y="24" text-anchor="middle" fill="#faf7f0" font-size="24">S</text></svg>',
        encoding='utf-8')
    cards = []
    for world_id, info, scenes, audio_dir, chronicle in worlds:
        directory = out / 'world' / world_id
        directory.mkdir(parents=True)
        # Encode filenames as URLs after collecting source paths.
        for scene in scenes:
            if scene['backdrop']:
                scene['backdrop'] = quote(scene['backdrop'])
            scene['sprite_files'] = {name: quote(file) if file else None
                                     for name, file in scene['sprite_files'].items()}
            for views in scene['sprite_views'].values():
                for item in views.values():
                    item['file'] = quote(item['file'])
            for beat in scene['beats']:
                if beat['audio_url']:
                    filename = beat['audio_url'].removeprefix('audio/')
                    target = directory / 'audio' / filename
                    target.parent.mkdir(exist_ok=True)
                    shutil.copyfile(audio_dir / filename, target)
        context = theater_context(world_id, scenes)
        context.update(static_site=True, index_url='../../index.html')
        (directory / 'theater.html').write_text(
            templates.get_template('theater.html').render(context), encoding='utf-8')
        chronicle.update(static_site=True, index_url='../../index.html')
        (directory / 'chronicle.html').write_text(
            templates.get_template('chronicle.html').render(chronicle), encoding='utf-8')
        (directory / 'theater.json').write_text(json.dumps(dict(scenes=scenes), ensure_ascii=False), encoding='utf-8')
        cards.append(dict(id=world_id, characters=[display_name(name, travelers) for name in info.characters],
                          place=locations.get(info.location, info.location), days=sorted({s['day'] for s in scenes}),
                          scenes=len(scenes), threads=len(chronicle['chronicle'].threads)))
    (out / 'index.html').write_text(templates.get_template('export_index.html').render(
        static_site=True, index_url='index.html', worlds=cards, notice=NOTICE), encoding='utf-8')
    (out / 'export-manifest.json').write_text(ExportManifest(
        # the site is public: an asset root inside the repo is recorded relative to it, not as a local path
        asset_root=(assets.resolve().relative_to(Path.cwd().resolve()).as_posix()
                    if assets.resolve().is_relative_to(Path.cwd().resolve()) else str(assets.resolve())),
        assets=sorted(referenced)).model_dump_json(indent=2), encoding='utf-8')
