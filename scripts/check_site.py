#!/usr/bin/env python3
"""Check static theater links, embedded data, and copied asset provenance (stdlib only)."""

import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


def data_urls(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'audio_url', 'backdrop', 'file'} and isinstance(item, str):
                yield item
            elif key == 'sprite_files':
                yield from (url for url in item.values() if url)
            else:
                yield from data_urls(item)
    elif isinstance(value, list):
        for item in value:
            yield from data_urls(item)


class PageLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.script = None
        self.buffer = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.urls.extend(value for key, value in attrs.items() if key in {'href', 'src'} and value)
        if tag == 'script':
            self.script = attrs.get('type', 'javascript')
            self.buffer = ''

    def handle_data(self, data):
        if self.script:
            self.buffer += data

    def handle_endtag(self, tag):
        if tag != 'script' or not self.script:
            return
        if self.script == 'application/json':
            self.urls.extend(data_urls(json.loads(self.buffer)))
        else:
            # The shared template embeds its JSON values in JS declarations.
            for match in re.finditer(r'\b(?:const|let)\s+\w+\s*=\s*', self.buffer):
                try:
                    value, _ = json.JSONDecoder().raw_decode(self.buffer[match.end():])
                except ValueError:
                    continue
                self.urls.extend(data_urls(value))
        self.script = None


def check_site(root: Path) -> list[str]:
    root = root.resolve()
    errors = []
    if not (root / 'index.html').is_file():
        errors.append('missing index.html')
    for path in sorted(root.rglob('*')):
        if path.suffix == '.html':
            parser = PageLinks()
            parser.feed(path.read_text())
            urls = parser.urls
        elif path.suffix == '.json' and path.name != 'export-manifest.json':
            urls = list(data_urls(json.loads(path.read_text())))
        else:
            continue
        for url in urls:
            parsed = urlsplit(url)
            if parsed.scheme or parsed.netloc or parsed.path.startswith('/') or '\\' in url:
                errors.append(f'{path.relative_to(root)}: non-relative URL {url}')
                continue
            if not parsed.path:  # Same-page chapter anchor.
                continue
            target = (path.parent / unquote(parsed.path)).resolve()
            if not target.is_relative_to(root) or not target.is_file():
                errors.append(f'{path.relative_to(root)}: missing file {url}')
    manifest_path = root / 'export-manifest.json'
    if not manifest_path.is_file():
        errors.append('missing export-manifest.json')
    else:
        manifest = json.loads(manifest_path.read_text())
        asset_root = Path(manifest['asset_root']).resolve()
        player = Path(__file__).resolve().parents[1] / 'assets/player'
        copied = {p.relative_to(root / 'assets').as_posix() for p in (root / 'assets').rglob('*') if p.is_file()}
        if copied != set(manifest['assets']):
            errors.append('copied assets differ from export manifest')
        for filename in manifest['assets']:
            target = root / 'assets' / filename
            source = asset_root / filename
            if not source.is_file() or not target.is_file() or source.read_bytes() != target.read_bytes():
                errors.append(f'asset differs from selected root: {filename}')
        if asset_root != player.resolve():
            player_hashes = {hashlib.sha256(p.read_bytes()).digest() for p in player.rglob('*')
                             if p.is_file() and p.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}}
            for filename in copied:
                if hashlib.sha256((root / 'assets' / filename).read_bytes()).digest() in player_hashes:
                    errors.append(f'file copied from assets/player: {filename}')
    return sorted(set(errors))


if __name__ == '__main__':
    errors = check_site(Path(sys.argv[1]))
    for error in errors:
        print(error)
    print(f'{sum("missing" in error for error in errors)} missing files; '
          f'{sum("copied from assets/player" in error for error in errors)} files copied from assets/player; '
          f'{len(errors)} errors')
    sys.exit(bool(errors))
