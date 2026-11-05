"""Attempts travel before their encounter and scene, without model calls."""
import asyncio
from types import SimpleNamespace

import pytest

from story_engine.agents.character import Action, Plan
from story_engine.config import load_configs
from story_engine.simulation import run_tick
from story_engine.trace import TraceWriter
from story_engine.world.io import create_world, load_state, read_events, read_scenes
from story_engine.world.models import CharacterState, Clock, Person, Place, WorldState


@pytest.mark.parametrize('destination', ['spot', 'person', 'stay'])
def test_attempt_destination(tmp_path, destination):
    state = WorldState(clock=Clock(day=1, part='morning'),
        places=[Place(slug='montwise', details=[])],
        characters={'osvald': CharacterState(where='montwise', spot='the_well',
                                           goals=['Study'], commitments=[])},
        people={'Librarian': Person(where='montwise', spot='library_exterior',
                                    wants=['Study'], commitments=[])}, situations=[])
    world = create_world(['osvald'], 'montwise', 'Study', state, worlds_dir=tmp_path / 'worlds')
    run = tmp_path / 'run'
    run.mkdir()
    fields = ({'where': 'montwise', 'spot': 'library_exterior'} if destination == 'spot'
              else {'seek': 'Librarian'} if destination == 'person' else {})
    expected = 'the_well' if destination == 'stay' else 'library_exterior'

    class Character:
        async def choose(self, *_):
            return Plan(call='plan', kind='attempt', intent='Study', aim='Ask about books', **fields)
        async def act(self, *_, **kwargs):
            return Action(call='action', intent='Study', move='wait', urge=0, action='', say='')

    async def adjudicate(current, *_):
        assert current.characters['osvald'].spot == expected
        encounters = [SimpleNamespace(mains=['osvald'], minor=['Librarian'])] if destination == 'person' else []
        return None, encounters, current

    scene_spots = []
    async def round_(current, *_, **kwargs):
        scene_spots.append(current.characters['osvald'].spot)
        return None, {}, current

    async def offscreen(current, *_):
        return [], current, {}

    session = SimpleNamespace(active=True, world_dir=world, run_dir=run, day=1,
        characters={'osvald': Character()}, scene_notes={}, settings=load_configs()[1],
        trace=TraceWriter(run), world=SimpleNamespace(adjudicate=adjudicate, round=round_),
        offscreen=SimpleNamespace(offscreen=offscreen))
    result = asyncio.run(run_tick(world, run, session=session))
    assert result.characters['osvald'].spot == expected
    scenes = read_scenes(world)
    assert len(scenes) == 1 and scenes[0].spot == expected
    assert scenes[0].participants == (['osvald', 'Librarian'] if destination != 'stay' else ['osvald'])
    assert scene_spots and set(scene_spots) == {expected}
    moves = [e for e in read_events(world) if e.actor == 'osvald' and e.ops]
    assert len(moves) == (destination != 'stay')
    if moves:
        assert moves[0].ops[0].op == 'move' and moves[0].ops[0].spot == expected
        assert moves[0].content == ('osvald goes to find Librarian.' if destination == 'person'
                                    else 'osvald goes to montwise.')
    assert result == load_state(world)


@pytest.mark.parametrize('fields,expected', [
    ({'where': 'cropdale', 'spot': 'tavern', 'seek': 'agnea'}, 'valid'),
    ({'where': 'missing'}, 'where'),
    ({'where': 'cropdale', 'spot': 'missing'}, 'spot'),
    ({'seek': 'missing'}, 'seek'),
])
def test_attempt_field_checks(tmp_path, monkeypatch, fields, expected):
    import json
    from test_character_action import setup_agent

    reply = json.dumps(dict(call='plan', kind='attempt', intent='Study', aim='Study', **fields))
    agent, _, requests, _, _ = setup_agent(tmp_path, monkeypatch, iter([reply, reply]))

    async def choose():
        async with agent:
            return await agent.choose('morning', [])

    result = asyncio.run(choose())
    if expected == 'valid':
        assert (result.where, result.spot, result.seek) == ('cropdale', 'tavern', 'agnea')
    else:
        assert getattr(result, expected) is None
    assert len(requests) == (1 if expected == 'valid' else 2)


@pytest.mark.parametrize('case', ['empty', 'occupied', 'retry', 'unfilled', 'go', 'other_main'])
@pytest.mark.parametrize('spot', ['library_exterior', None])
def test_empty_attempt_encounter(tmp_path, monkeypatch, case, spot):
    import json
    import jsonschema
    from pathlib import Path
    from claude_agent_sdk import ResultMessage
    from sdk_sessions import resumable_fake
    from world_replies import round_reply
    from story_engine.agents import character, world as world_agent
    from story_engine.agents.sdk import json_schema_output, require_person_sex
    from story_engine.simulation import TickSession
    from story_engine.stages import catalog_schema, load_catalogs

    root = Path(__file__).resolve().parents[2]
    characters = {'osvald': CharacterState(where='montwise', spot='the_well', goals=['Study'], commitments=[])}
    if case == 'other_main':
        characters['temenos'] = characters['osvald'].model_copy()
    state = WorldState(clock=Clock(day=1, part='morning'),
        places=[Place(slug='montwise', details=[])], characters=characters,
        people={'Librarian': Person(where='montwise', spot=spot, wants=['Study'], commitments=[])}
               if case == 'occupied' else {}, situations=[])
    world = create_world(list(characters), 'montwise', 'Study', state, worlds_dir=tmp_path / 'worlds')
    run = tmp_path / 'run'
    run.mkdir()
    (world / 'scene_context.md').write_text('Study.')
    captured = []
    requires_person = case not in {'occupied', 'go', 'other_main'}
    introduce = dict(op='introduce', name='Visitor', sex='f', where='montwise',
                     spot=spot, wants=['Study'], commitments=[])

    class FakeClient:
        def __init__(self, *, options):
            self.options = options
            self.call = None
            self.encounter_calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            try:
                self.request = json.loads(request)
                self.call = self.request.get('call')
            except json.JSONDecodeError:
                pass
            if self.call == 'adjudicate':
                self.encounter_calls += 1
                captured.append((self.options.output_format, self.request))

        async def receive_response(self):
            if self.call == 'adjudicate':
                ops = [introduce] if requires_person and case != 'unfilled' else []
                if case == 'retry' and self.encounter_calls == 1:
                    ops = []
                reply = dict(call='adjudicate', encounters=[], ops=ops)
            elif self.call == 'scene_round':
                reply = round_reply(self.request)
            elif self.call == 'offscreen':
                reply = dict(call='offscreen', events=[], situation_notes={})
            elif self.call == 'part_of_day':
                reply = dict(call='plan', kind='go' if case == 'go' else 'attempt',
                             intent='Study', aim='Ask about books', where='montwise', spot=spot)
            else:
                reply = dict(call='action', intent='Study', move='wait', urge=0, action='', say='')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(reply))

    fake = resumable_fake(FakeClient)
    monkeypatch.setattr(character, 'ClaudeSDKClient', fake)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', fake)

    async def exercise():
        async with TickSession(world, run, root=root) as session:
            await run_tick(world, run, session=session)
    asyncio.run(exercise())
    output, request = captured[0]
    baseline = catalog_schema(require_person_sex(json_schema_output(world_agent.AdjudicateReply)),
                              load_catalogs(root))
    if requires_person:
        assert request['empty_attempt_spots'] == [dict(place='montwise', spot=spot)]
        schema = output['schema']
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(dict(call='adjudicate', ops=[]), schema)
        for wrong in [dict(introduce, where='cropdale'), dict(introduce, spot='the_well')]:
            with pytest.raises(jsonschema.ValidationError):
                jsonschema.validate(dict(call='adjudicate', ops=[wrong]), schema)
        jsonschema.validate(dict(call='adjudicate', ops=[introduce]), schema)
        assert len(captured) == (2 if case in {'retry', 'unfilled'} else 1)
        assert read_scenes(world)[0].participants == (['osvald'] if case == 'unfilled'
                                                      else ['osvald', 'Visitor'])
        rows = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
        assert any(row['type'] == 'empty_spot_unfilled' for row in rows) == (case == 'unfilled')
    else:
        assert output == baseline
        assert 'empty_attempt_spots' not in request
