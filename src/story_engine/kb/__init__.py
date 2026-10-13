"""KB slug normalization and generate input validation."""

from difflib import get_close_matches
from pathlib import Path
import unicodedata


TRAVELERS = frozenset({
    "osvald", "temenos", "agnea", "throne",
    "hikari", "ochette", "castti", "partitio",
})


def normalize_slug(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.lower()).encode("ascii", "ignore").decode("ascii")
    return folded.strip().replace(" ", "_")


def location_slugs() -> set[str]:
    return {path.stem for path in Path("kb/locations").rglob("*.md") if path.is_file()}


def validate_input(characters: str, location: str) -> tuple[list[str], str]:
    raw_characters = characters.split(",")
    slugs = [normalize_slug(character) for character in raw_characters]
    location_slug = normalize_slug(location)
    if not 2 <= len(slugs) <= 3:
        raise ValueError(f"--characters {characters!r}: expected 2-3 distinct travelers")
    seen = set()
    for raw, slug in zip(raw_characters, slugs):
        if slug not in TRAVELERS:
            raise ValueError(f"--characters: unknown traveler {raw!r} (slug {slug!r})")
        if slug in seen:
            raise ValueError(f"--characters: repeated traveler {raw!r} (slug {slug!r}); expected distinct travelers")
        seen.add(slug)
    locations = location_slugs()
    if location_slug not in locations:
        suggestions = get_close_matches(location_slug, sorted(locations), n=3, cutoff=0)
        hint = f"closest location slugs: {', '.join(suggestions)}" if suggestions else "no location files found under kb/locations/"
        raise ValueError(f"--location: unknown location {location!r} (slug {location_slug!r}); {hint}")
    return slugs, location_slug
