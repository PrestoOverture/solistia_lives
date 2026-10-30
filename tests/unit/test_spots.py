"""W-spot: live choices use catalog ids; historical artifacts stay replayable."""
from story_engine.agents.sdk import require_person_sex
import asyncio
import json
from pathlib import Path

import pytest

from story_engine.agents.character import CharacterReply, Plan
from story_engine.agents.sdk import json_schema_output
from story_engine.agents.world import WorldAgent, WorldReply, OffscreenReply, OffscreenAgent
from story_engine.stages import catalog_schema, load_catalogs, validate_spot
from story_engine.world.io import load_state
from story_engine.world.models import Place, WorldState
from test_character_action import setup_agent
from test_event_drops import workspace, open_agent, rows
from test_day_start import fake_sdk, situation

ROOT = Path(__file__).resolve().parents[2]


def spot_nodes(node):
    if isinstance(node, dict):
        if 'spot' in node.get('properties', {}):
            yield node
        for value in node.values():
            yield from spot_nodes(value)
    elif isinstance(node, list):
        for value in node:
            yield from spot_nodes(value)


@pytest.mark.parametrize('reply_type', [CharacterReply, WorldReply, OffscreenReply])
def test_schema_spot_enums_exactly_catalog_ids(reply_type):
    catalogs = load_catalogs(ROOT)
    schema = catalog_schema(json_schema_output(reply_type), catalogs)['schema']
    nodes = [node for node in spot_nodes(schema) if 'anyOf' in node and 'enum' in node['properties']['spot']]
    assert nodes
    expected = {s.id for c in catalogs.values() for s in c.spots} | {None}
    for node in nodes:
        assert set(node['properties']['spot']['enum']) == expected
        variants = node['anyOf']
        for place, catalog in catalogs.items():
            branch = next(v for v in variants if any(p.get('const') == place
                          for p in v['properties'].values()))
            assert set(branch['properties']['spot']['enum']) == {s.id for s in catalog.spots} | {None}
        assert variants[-1] == {'properties': {'spot': {'type': 'null'}}}
    # With no catalogs, even a schema-only provider has no non-null choice.
    empty = catalog_schema(json_schema_output(reply_type), {})['schema']
    assert all(node['properties']['spot']['enum'] == [None]
               for node in spot_nodes(empty) if 'enum' in node['properties']['spot'])


def test_schema_rejects_other_place_and_uncatalogued_place():
    # jsonschema is already used optionally by test_structured_output, not a new dependency.
    jsonschema = pytest.importorskip('jsonschema')
    schema = catalog_schema(json_schema_output(Plan), load_catalogs(ROOT))['schema']
    plan = dict(call='plan', kind='go', intent='Visit', aim='Visit', where='montwise', spot='library_exterior')
    jsonschema.validate(plan, schema)
    for where, spot in [('cropdale', 'library_exterior'), ('no_catalog', 'town_square'),
                        ('montwise', 'free text')]:
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({**plan, 'where': where, 'spot': spot}, schema)
    jsonschema.validate({**plan, 'where': 'no_catalog', 'spot': None}, schema)


@pytest.mark.parametrize('place,spot', [('festival_grounds', 'watermill_bridge'),
                                      ('no_catalog', 'town_square')])
@pytest.mark.parametrize('corrected', [False, True])
def test_plan_reference_retry_then_null_and_prompt(tmp_path, monkeypatch, place, spot, corrected):
    bad = dict(call='plan', kind='go', intent='Visit', aim='Visit', where=place, spot=spot)
    good = {**bad, 'spot': 'dance_stage' if place == 'festival_grounds' else None}
    agent, instances, requests, _, run = setup_agent(
        tmp_path, monkeypatch, iter(map(json.dumps, [bad, good if corrected else bad])))
    state = load_state(agent.world_dir)
    state.places.append(Place(slug='no_catalog', details=[]))
    # Keep model instances validated when adding the fixture-only place.
    state = WorldState.model_validate(state.model_dump())
    (agent.world_dir / 'genesis.json').write_text(state.model_dump_json())

    async def exercise():
        async with agent:
            return await agent.choose('morning', [])

    result = asyncio.run(exercise())
    assert result.spot == (good['spot'] if corrected else None)
    assert len(requests) == 2 and 'must be a catalog id for place' in requests[1]
    request = json.loads(requests[0])
    catalogs = load_catalogs(ROOT)
    assert request['spots']['no_catalog'] == []
    for p in state.places:
        expected = [s.model_dump(include={'id', 'name', 'about'}) for s in catalogs[p.slug].spots] if p.slug in catalogs else []
        assert request['spots'][p.slug] == expected
        for item in expected:
            assert item['name'] and item['about']
    assert instances[0].options.output_format == catalog_schema(json_schema_output(CharacterReply), catalogs)
    assert 'watermill_bridge' not in instances[0].options.system_prompt
    assert len(rows(run, 'plan_spot_cleared')) == (not corrected)


@pytest.mark.parametrize('place', ['cropdale', 'no_catalog'])
def test_data_reference_check(place):
    catalogs = load_catalogs(ROOT)
    validate_spot(catalogs, place, None)
    with pytest.raises(ValueError, match='must be a catalog id'):
        validate_spot(catalogs, place, 'library_exterior')


@pytest.mark.parametrize('call', ['adjudicate', 'day_start', 'scene_round', 'minor', 'offscreen'])
@pytest.mark.parametrize('corrected', [False, True])
def test_world_spot_ops_retry_then_drop(workspace, monkeypatch, call, corrected):
    world, run = workspace
    state = load_state(world)
    valid_spot = 'festival_clearing'
    bad_spot = 'library_exterior'  # exists, but belongs to Montwise

    def respond(client, request):
        spot = valid_spot if corrected and len(client.calls) == 2 else bad_spot
        introduce = dict(op='introduce', name='Visitor', where='festival_grounds', spot=spot, wants=['Visit'])
        move = dict(op='move', who='Host', place='festival_grounds', spot=spot)
        if call == 'adjudicate':
            return dict(call=call, ops=[introduce])
        if call == 'day_start':
            return dict(call=call, ops=[introduce, dict(op='open', situation=situation())])
        if call == 'minor':
            return dict(call='scene_round', minor_moves={'Host': dict(move='act', urge=2,
                        action='Host walks.', ops=[move])})
        if call == 'scene_round':
            return dict(call=call, ops=[move])
        return dict(call='offscreen', events=[dict(place='festival_grounds', ops=[move])])

    clients = fake_sdk(monkeypatch, respond)

    async def exercise():
        async with open_agent(workspace, OffscreenAgent if call == 'offscreen' else WorldAgent) as agent:
            if call == 'adjudicate':
                event, _, updated = await agent.adjudicate(state, {}, [])
            elif call == 'day_start':
                updated = await agent.day_start(state, [])
                assert ('Visitor' in updated.people) == corrected
                return
            elif call in {'scene_round', 'minor'}:
                event, minors, updated = await agent.round(state, [], place='festival_grounds',
                    main_present=['agnea'], minor_present=['Host'], last_winner=None, scene='1', round_number=1)
                if call == 'minor':
                    assert ('Host' in minors) == corrected
                    if corrected:
                        assert minors['Host'].ops[0].spot == valid_spot
                    return
            else:
                events, updated, _ = await agent.offscreen(state, set())
                assert bool(events) == corrected
                event = events[0] if events else None
            assert (event is not None) == corrected
            if corrected:
                assert event.ops[0].spot == valid_spot
            else:
                assert updated == state

    asyncio.run(exercise())
    assert len(clients[0].calls) == 2 and 'must be a catalog id' in clients[0].calls[1]
    assert len(rows(run, 'event_dropped')) == (not corrected)
    assert clients[0].options.output_format == catalog_schema(
        require_person_sex(json_schema_output(OffscreenReply if call == 'offscreen' else WorldReply)), load_catalogs(ROOT))


@pytest.mark.parametrize('corrected', [False, True])
def test_initializer_spots_retry_then_null(workspace, monkeypatch, corrected):
    from story_engine.agents import character, initializer
    from story_engine.config import load_configs
    from story_engine.trace import TraceWriter

    world, run = workspace
    (run / 'scene_context.md').write_text((world / 'scene_context.md').read_text())
    initial = load_state(world)

    def respond(client, request):
        payload = initial.model_dump(exclude={'clock'})
        spot = 'festival_clearing' if corrected and len(client.calls) == 2 else 'library_exterior'
        payload['characters']['agnea']['spot'] = spot
        payload['people']['Host']['spot'] = spot
        return payload

    clients = fake_sdk(monkeypatch, respond)
    monkeypatch.setattr(initializer, 'ClaudeSDKClient', character.ClaudeSDKClient)
    monkeypatch.setattr(initializer, 'record_api_host', lambda *_: None)
    models, settings = load_configs()
    state = asyncio.run(initializer.starting_state(ROOT, run, list(initial.characters),
        'festival_grounds', 'A festival', models.initializer, settings.agent_max_turns, TraceWriter(run)))
    assert state.characters['agnea'].spot == state.people['Host'].spot == ('festival_clearing' if corrected else None)
    assert len(clients[0].calls) == 2 and 'must be a catalog id' in clients[0].calls[1]
    schema = clients[0].options.output_format['schema']
    assert schema['$defs']['CharacterState']['properties']['spot']['enum']


@pytest.mark.parametrize('corrected', [False, True])
def test_offscreen_perception_spot_retry_then_null(workspace, monkeypatch, corrected):
    state = load_state(workspace[0])

    def respond(client, request):
        spot = 'festival_clearing' if corrected and len(client.calls) == 2 else 'library_exterior'
        return dict(call='offscreen', events=[dict(place='festival_grounds', spot=spot, content='A bell rings.')])

    clients = fake_sdk(monkeypatch, respond)

    async def exercise():
        async with open_agent(workspace, OffscreenAgent) as agent:
            events, _, _ = await agent.offscreen(state, set())
            return events

    events = asyncio.run(exercise())
    assert len(clients[0].calls) == 2 and 'must be a catalog id' in clients[0].calls[1]
    assert events[0].perceived_by == ([] if corrected else list(state.characters))
    assert len(rows(workspace[1], 'offscreen_spot_cleared')) == (not corrected)
