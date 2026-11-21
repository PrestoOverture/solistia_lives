"""KB slug normalization and generate input validation."""

from collections.abc import Iterable
from difflib import get_close_matches
from pathlib import Path
import unicodedata

import frontmatter


TRAVELERS = frozenset({
    "osvald", "temenos", "agnea", "throne",
    "hikari", "ochette", "castti", "partitio",
})


def normalize_slug(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")
    return folded.strip().replace(" ", "_")


def kb_display_name(path: Path) -> str:
    metadata = frontmatter.load(path)
    name = metadata.get("name", path.stem)
    return (metadata.get("aliases") or [name])[0] if name == path.stem else name


def kb_names(root: Path, mains: Iterable[str]) -> tuple[dict[str, str], dict[str, str]]:
    names = {slug: kb_display_name(root / "kb/characters" / slug / f"{slug}.md") for slug in mains}
    places = {path.stem: kb_display_name(path) for path in (root / "kb/locations").rglob("*.md")}
    return names, places


def location_regions(root: Path = Path(".")) -> dict[str, str]:
    """Each KB location's region, the first directory under kb/locations/."""
    base = root / "kb/locations"
    return {path.stem: path.relative_to(base).parts[0]
            for path in base.rglob("*.md") if path.is_file() and len(path.relative_to(base).parts) > 1}


def location_slugs(root: Path = Path(".")) -> set[str]:
    return {path.stem for path in (root / "kb/locations").rglob("*.md") if path.is_file()}


def validate_input(characters: str, location: str, setting: Path = Path("."), *,
                   mains: frozenset[str] | None = None) -> tuple[list[str], str]:
    raw_characters = characters.split(",")
    slugs = [normalize_slug(character) for character in raw_characters]
    location_slug = normalize_slug(location)
    if not 2 <= len(slugs) <= 3:
        raise ValueError(f"--characters {characters!r}: expected 2-3 distinct travelers")
    if mains is None:
        mains = frozenset(card.stem for card in (setting / "cards").glob("*.md") if card.is_file())
    seen = set()
    for raw, slug in zip(raw_characters, slugs):
        if slug not in mains:
            raise ValueError(f"--characters: unknown traveler {raw!r} (slug {slug!r})")
        if slug in seen:
            raise ValueError(f"--characters: repeated traveler {raw!r} (slug {slug!r}); expected distinct travelers")
        seen.add(slug)
    locations = location_slugs(setting)
    if location_slug not in locations:
        suggestions = get_close_matches(location_slug, sorted(locations), n=3, cutoff=0)
        hint = f"closest location slugs: {', '.join(suggestions)}" if suggestions else "no location files found under kb/locations/"
        raise ValueError(f"--location: unknown location {location!r} (slug {location_slug!r}); {hint}")
    return slugs, location_slug
