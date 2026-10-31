"""Initializer place enums constrain model replies alongside catalog spot choices."""

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest

from story_engine.agents import initializer
from story_engine.config import load_configs
from story_engine.trace import TraceWriter

ROOT = Path(__file__).resolve().parents[2]


def test_initializer_output_schema_restricts_every_place_field(tmp_path, monkeypatch):
    (tmp_path / 'scene_context.md').write_text('## Context\nA festival.')
    schemas = []

    class Captured(Exception):
        pass

    class FakeClient:
        def __init__(self, *, options):
            schemas.append(options.output_format['schema'])
            raise Captured

    monkeypatch.setattr(initializer, 'ClaudeSDKClient', FakeClient)
    monkeypatch.setattr(initializer, 'record_api_host', lambda *_: None)
    models, settings = load_configs(ROOT / 'config/models.yaml')
    with pytest.raises(Captured):
        asyncio.run(initializer.starting_state(
            ROOT, tmp_path, ['agnea', 'throne'], 'cropdale', 'A festival',
            models.initializer, settings.agent_max_turns, TraceWriter(tmp_path),
        ))
    schema = schemas[0]
    commitment = dict(what='Help at the tavern', where='cropdale', day=1, part='evening')
    valid = dict(
        places=[dict(slug='cropdale', details=[])],
        characters={name: dict(where='cropdale', spot='village_square', goals=['Visit'],
                               commitments=[deepcopy(commitment)])
                    for name in ['agnea', 'throne']},
        people={'Gus': dict(where='cropdale', spot='tavern', sex='m', wants=['Serve supper'],
                            commitments=[deepcopy(commitment)])},
        situations=[dict(id='supper', kind='promise', summary='Supper at the tavern',
                         touches=['agnea'], people=['Gus'], status='open',
                         next='Supper is served', due=dict(day=1, part='evening'))],
    )
    jsonschema.validate(valid, schema)

    # Exact attempt-1 raw_reply from runs/20261031-081129-44e714/trace.jsonl
    # (agnea_throne_2): catalog spot ids in places, with cropdale absent.
    recorded = json.loads((ROOT / 'tests/fixtures/initializer/agnea_throne_2.json').read_text())
    assert 'cropdale' not in {place['slug'] for place in recorded['places']}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(recorded, schema)

    paths = [
        ('places', 0, 'slug'),
        ('characters', 'agnea', 'where'),
        ('people', 'Gus', 'where'),
        ('characters', 'agnea', 'commitments', 0, 'where'),
        ('people', 'Gus', 'commitments', 0, 'where'),
    ]
    for path in paths:
        for invalid in ['village_square', 'Cropdale tavern']:
            reply = deepcopy(valid)
            # Exercise the catalog anyOf's null-spot branch too: it must not
            # bypass the place enum for character or person whereabouts.
            reply['characters']['agnea']['spot'] = None
            reply['people']['Gus']['spot'] = None
            field = reply
            for key in path[:-1]:
                field = field[key]
            field[path[-1]] = invalid
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(reply, schema)

    # Place enums must preserve the catalog's place/spot pairing rules.
    wrong_spot = deepcopy(valid)
    wrong_spot['characters']['agnea']['spot'] = 'library_exterior'
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(wrong_spot, schema)
    null_spot = deepcopy(valid)
    null_spot['characters']['agnea']['spot'] = None
    jsonschema.validate(null_spot, schema)
