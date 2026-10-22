"""Accent/case folding shared by whereabouts matching (D27: no other text heuristics)."""

import unicodedata


def fold(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFKD", value.casefold())
                   if not unicodedata.combining(char))
