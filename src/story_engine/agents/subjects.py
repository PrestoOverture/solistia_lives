"""Shared main-character names and unquoted sentence boundaries."""

import re
import unicodedata
from pathlib import Path

import yaml


def fold(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value.casefold())
                   if not unicodedata.combining(char))


def main_names(root: Path, characters) -> set[str]:
    names = set()
    for slug in characters:
        text = (root / "kb" / "characters" / slug / f"{slug}.md").read_text(encoding="utf-8")
        metadata = yaml.safe_load(text.split("---", 2)[1])
        names.update(fold(name) for name in [metadata["name"], *metadata.get("aliases", [])])
        card = (root / "cards" / f"{slug}.md").read_text(encoding="utf-8")
        names.update(fold(name.strip()) for name in re.findall(r"^# (.+)$", card, re.MULTILINE))
    return names


def sentences(text: str) -> list[str]:
    unquoted = re.sub(r'"[^"]*"|“[^”]*”', '', text)
    return re.split(r'(?<=[.!?])\s+|\n+', unquoted)


def starts_with_name(text: str, names: set[str]) -> bool:
    start = fold(text.lstrip(' \t\r\"“”‘’'))
    return any(re.match(re.escape(name) + r"(?!\w)", start) for name in names)


def word_count(text: str) -> int:
    """Word count = whitespace-split tokens (D23)."""
    return len(text.split())
