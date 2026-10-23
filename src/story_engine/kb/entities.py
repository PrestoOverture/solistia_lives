"""Deterministic KB entity matching and conservative sentence selection."""

from pathlib import Path
import re
import unicodedata

import frontmatter
from pydantic import BaseModel

from story_engine.kb import normalize_slug


class EntitySentence(BaseModel):
    sentence_id: int | None = None
    text: str
    entities: list[str]


def _fold(text: str) -> tuple[str, list[int]]:
    """Reuse slug ASCII folding, retaining whitespace and source offsets."""
    folded = []
    offsets = []
    for index, char in enumerate(text):
        value = char.encode("ascii", "ignore").decode() if char.isspace() else normalize_slug(char)
        folded.append(value)
        offsets.extend([index] * len(value))
    return "".join(folded), offsets


def entity_dictionary(kb_root: Path = Path("kb")) -> dict[str, set[str]]:
    """Map folded frontmatter names and aliases to their KB filename slugs."""
    dictionary: dict[str, set[str]] = {}
    for path in sorted(kb_root.rglob("*.md")):
        metadata = frontmatter.load(path).metadata
        names = [metadata.get("name", ""), *metadata.get("aliases", [])]
        for name in names:
            alias = _fold(name)[0].strip()
            if alias:
                dictionary.setdefault(alias, set()).add(normalize_slug(path.stem))
    return dictionary


def _mentions(text: str, dictionary: dict[str, set[str]]) -> list[tuple[int, int, set[str]]]:
    folded, offsets = _fold(text)
    candidates = []
    for alias, slugs in dictionary.items():
        if not alias:
            continue
        for match in re.finditer("(?=(" + re.escape(alias) + "))", folded):
            start, end = offsets[match.start(1)], offsets[match.end(1) - 1] + 1
            while end < len(text) and unicodedata.combining(text[end]):
                end += 1
            # Check the original characters: ASCII folding removes curly
            # apostrophes and dashes, which must still act as word boundaries.
            if start and (text[start - 1].isalnum() or text[start - 1] == "_"):
                continue
            if end < len(text) and (text[end].isalnum() or text[end] == "_"):
                continue
            candidates.append((start, end, slugs))
    # Resolve overlaps by length before restoring textual mention order.
    chosen = []
    for mention in sorted(candidates, key=lambda item: (-(item[1] - item[0]), item[0])):
        start, end, _ = mention
        if not any(start < other_end and other_start < end for other_start, other_end, _ in chosen):
            chosen.append(mention)
    return sorted(chosen, key=lambda item: item[0])


_QUOTES = re.compile(r'"[^"]*"|“[^”]*”|(?<!\w)\'[^\n]*?\'(?!\w)|‘[^’]*’')
_BOUNDARIES = re.compile(r'''[.!?]+["”’')\]]*(?=\s|$)|\n[ \t]*\n''')


def prefilter(text: str, dictionary: dict[str, set[str]]) -> list[EntitySentence]:
    """Keep entity-bearing sentences, preserving original prose and dialogue.

    Quoted passages and their attribution stay together. A following quotation
    in the same paragraph is kept with its lead-in, conservatively retaining
    dialogue continuations even when they contain multiple grammatical sentences.
    Slugs sharing one alias have tied mention positions and are sorted by slug.
    """
    mentions = _mentions(text, dictionary)
    quotes = [match.span() for match in _QUOTES.finditer(text)]
    spans = []
    start = 0
    for boundary in _BOUNDARIES.finditer(text):
        end = boundary.end()
        if any(left <= boundary.start() and end < right for left, right, _ in mentions):
            continue
        paragraph_break = boundary.group().startswith("\n")
        if not paragraph_break:
            following = text[end:].lstrip()
            gap = text[end:len(text) - len(following)]
            if any(left <= boundary.start() < right for left, right in quotes):
                # A closing quote can end a sentence, but an attribution belongs
                # with it (e.g. '"Ready?" Osvald asked.'). Keep ambiguous cases.
                if any(left <= boundary.start() and end < right for left, right in quotes):
                    continue
                if following and not following[0].isupper():
                    continue
                if re.match(r"\w+\s+(?:said|asked|replied|whispered|shouted)\b", following):
                    continue
            if following.startswith(('"', '“', "'", '‘')) and "\n\n" not in gap:
                continue
        spans.append((start, end))
        start = end
    spans.append((start, len(text)))

    result = []
    for start, end in spans:
        entities = []
        for left, right, slugs in mentions:
            if start <= left and right <= end:
                for slug in sorted(slugs):
                    if slug not in entities:
                        entities.append(slug)
        if entities:
            result.append(EntitySentence(text=text[start:end].strip(), entities=entities))
    return result
