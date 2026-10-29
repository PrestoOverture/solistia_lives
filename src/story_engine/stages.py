"""Stage catalogs shared by simulation choices and the read-only player."""

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class StandPoint(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    h: float = Field(gt=0, le=1)


class StageSpot(BaseModel):
    id: str
    name: str = ''
    about: str = ''
    day: str | None = None
    night: str | None = None
    stand: list[StandPoint] = Field(min_length=1)


class StageCatalog(BaseModel):
    default: str
    spots: list[StageSpot]


def load_catalog(directory: Path, place: str) -> StageCatalog | None:
    if re.fullmatch(r'[A-Za-z0-9_-]+', place) is None:
        return None
    path = directory / 'stages' / f'{place}.yaml'
    try:
        if not path.resolve().is_relative_to(directory.resolve()):
            return None
        return StageCatalog.model_validate(yaml.safe_load(path.read_text()))
    except (OSError, ValueError, yaml.YAMLError):
        return None


def load_catalogs(root: Path) -> dict[str, StageCatalog]:
    directory = root / 'assets/player'
    return {path.stem: catalog for path in sorted((directory / 'stages').glob('*.yaml'))
            if (catalog := load_catalog(directory, path.stem)) is not None}


def spot_context(catalogs: dict[str, StageCatalog], places) -> dict:
    return {place: [spot.model_dump(include={'id', 'name', 'about'})
                    for spot in catalogs[place].spots] if place in catalogs else []
            for place in places}


def validate_spot(catalogs: dict[str, StageCatalog], place: str, spot: str | None) -> None:
    catalog = catalogs.get(place)
    if spot is not None and (catalog is None or spot not in {item.id for item in catalog.spots}):
        raise ValueError(f'spot {spot!r} must be a catalog id for place {place!r}, or null')


def validate_spot_ops(catalogs: dict[str, StageCatalog], ops) -> None:
    # Deliberately outside the reducer: historical free-text ops remain replayable.
    for op in ops:
        if op.op in {'move', 'introduce'}:
            validate_spot(catalogs, op.place if op.op == 'move' else op.where, op.spot)


def catalog_schema(output: dict, catalogs: dict[str, StageCatalog]) -> dict:
    """Constrain every spot field, including nested ops, without changing disk models.

    A session may introduce places, so include every catalog. The paired alternatives
    make an uncatalogued place null-only; code repeats the reference check for fakes
    and providers that do not enforce structured output.
    """
    ids = sorted({spot.id for catalog in catalogs.values() for spot in catalog.spots})

    def visit(node):
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            for value in list(node.values()):
                visit(value)
            properties = node.get('properties', {})
            if 'spot' not in properties:
                return
            properties['spot'] = {'enum': [*ids, None]}
            place_key = 'place' if 'place' in properties else 'where' if 'where' in properties else None
            if place_key:
                node['anyOf'] = [
                    {'properties': {place_key: {'const': place},
                                    'spot': {'enum': [*[s.id for s in catalog.spots], None]}},
                     'required': [place_key]}
                    for place, catalog in catalogs.items()
                ] + [{'properties': {'spot': {'type': 'null'}}}]
    visit(output['schema'])
    return output
