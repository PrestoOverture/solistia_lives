"""Deterministic D2/D28 guards exercised through a fake World SDK session."""

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from pydantic import ValidationError

from story_engine.agents import world as world_agent
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state, save_state
from story_engine.world.models import Person

ROOT = Path(__file__).resolve().parents[2]


def _settled(where, outcome, spot=None):
    return dict(status='settled', outcome=outcome, where=where, spot=spot)


def _staged(where, spot=None):
    return dict(status='staged', where=where, spot=spot)


def _adjudicate_reply(verdicts, encounters=None):
    return dict(call='adjudicate', verdicts=verdicts, encounters=encounters or [])


def _offscreen_reply(state, events=None, situation_notes=None):
    return dict(call='offscreen', events=events or [],
               people={name: person.model_dump() for name, person in state.people.items()},
               situations=[situation.model_dump(include={"id", "status", "next", "due", "people"}) for situation in state.situations],
               places=[place.model_dump() for place in state.places],
               situation_notes=situation_notes or {s.id: 'Unchanged.' for s in state.situations})


def _fake_client(replies, requests):
    class FakeClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            requests.append(request)

        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=next(replies))

    return FakeClient


def _run_resolve(world, run, monkeypatch, state, choices, replies):
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient',
                        _fake_client(iter([json.dumps(reply) for reply in replies]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            async with world_agent.OffscreenAgent(ROOT, run, world, models.world,
                                                  settings.agent_max_turns, TraceWriter(run)) as offscreen:
                return await agent.resolve(state, choices, [], offscreen=offscreen)

    return asyncio.run(exercise()), requests


def _run_round(world, run, monkeypatch, state, last_winner, reply):
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', _fake_client(iter([json.dumps(reply)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.round(state, [], place='festival_grounds',
                                     main_present=['agnea', 'throne'], minor_present=['Tam'],
                                     last_winner=last_winner)

    return asyncio.run(exercise()), requests


@pytest.mark.parametrize('case,scene,last_winner,content,event_type', [
    ('tick', False, None, 'The wind rises.', 'world'),
    ('subject', True, None, 'Throné rises.', 'world'),
    ('subject', True, None, "throne's hands move.", 'world'),
    ('subject', True, None, 'Agnea nods.', 'world'),
    ('subject', True, None, 'The Dancer smiles.', 'world'),
    ('quoted', True, None, '"Agnea! Over here," the boy calls.', 'world'),
    ('quoted', True, None, '“Agnea! Over here,” the boy calls.', 'world'),
    ('object', True, None, 'Gus hands Agnea a basket.', 'world'),
    ('speech', True, None, 'Agnea! There you are.', 'speech'),
    ('banner', True, None, "The Dancer's Blessing banner glows.", 'world'),
])
@pytest.mark.parametrize('actor', ['world', 'Gus'])
def test_world_content_accepted_with_no_text_judgment(tmp_path, monkeypatch, case, scene, last_winner, content, event_type, actor):
    """D27: code judges only schema and data references, never the wording of event content.
    A main character's name may start or appear anywhere in the content without being rejected."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    if scene:
        event = dict(place='festival_grounds', actor=actor, type=event_type,
                     content=content, perceived_by=['agnea'])
        reply = dict(call='scene_round', outcome=event, minor_moves={})
    else:
        event = dict(place='festival_grounds', actor=actor, type=event_type, content=content, intent=None)
        reply = _offscreen_reply(state, events=[event])
    replies = iter([json.dumps(reply)])
    requests = []

    class FakeClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            requests.append(request)

        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=next(replies))

    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', FakeClient)
    models, settings = load_configs()

    async def exercise():
        agent_type = world_agent.WorldAgent if scene else world_agent.OffscreenAgent
        async with agent_type(ROOT, run, world, models.world,
                              settings.agent_max_turns, TraceWriter(run)) as agent:
            if scene:
                return await agent.round(state, [], place='festival_grounds',
                                         main_present=['agnea', 'throne'], minor_present=[],
                                         last_winner=last_winner)
            return await agent.offscreen(state, {s.id for s in state.situations if s.status == 'open'})

    result = asyncio.run(exercise())
    failures = [row for row in map(json.loads, (run / 'trace.jsonl').read_text().splitlines())
                if row['type'] == 'world_validation_failed']
    assert len(requests) == 1 and not failures
    if scene:
        outcome, _minor_moves, _state = result
        assert outcome.content == content
    else:
        events, _updated, _notes = result
        assert events[0].content == content
    assert state == load_state(world)


def test_adjudicate_settled_outcome_event_and_staged_solo_scene(tmp_path, monkeypatch):
    """A settled verdict becomes an `of: <slug>` event at the verdict's place, and the
    character's `where`/`spot` match the verdict; a staged character left out of every
    encounter gets its own solo attempt encounter (D26, D28)."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    choices = {'agnea': {'where': 'cropdale', 'spot': None, 'aim': 'Visit the stalls.',
                        'intent': 'Buy some raspberries'},
              'throne': {'where': 'festival_grounds', 'spot': 'the raspberry thicket',
                        'aim': 'Search the thicket for the thief.', 'intent': 'Catch the thief'}}
    adjudicate = _adjudicate_reply({
        'agnea': _settled('cropdale', 'Agnea buys a basket of raspberries.'),
        'throne': _staged('festival_grounds', spot='the raspberry thicket'),
    })
    offscreen = _offscreen_reply(state)
    (events, updated, _notes, encounters, statuses), requests = _run_resolve(
        world, run, monkeypatch, state, choices, [adjudicate, offscreen])
    assert len(requests) == 2
    outcome = next(event for event in events if event.of == 'agnea')
    assert outcome.content == 'Agnea buys a basket of raspberries.'
    assert outcome.place == 'cropdale'
    assert updated.characters['agnea'].where == 'cropdale'
    assert updated.characters['throne'].where == 'festival_grounds'
    assert updated.characters['throne'].spot == 'the raspberry thicket'
    assert statuses == {'agnea': 'settled', 'throne': 'staged'}
    assert any(encounter.mains == ['throne'] for encounter in encounters)


def test_adjudicate_staged_verdict_with_outcome_fails_schema():
    """A staged verdict carries no outcome field (it is forbidden by the schema)."""
    with pytest.raises(ValidationError):
        world_agent.Staged.model_validate(
            dict(status='staged', where='cropdale', spot=None, outcome='Should not be allowed.'))
    with pytest.raises(ValidationError):
        world_agent.AdjudicateReply.model_validate(dict(
            call='adjudicate',
            verdicts={'throne': dict(status='staged', where='cropdale', spot=None, outcome='Nope.')},
            encounters=[]))


def test_offscreen_request_has_no_main_character_plan_or_intent(tmp_path, monkeypatch):
    """The off-screen request carries only off-screen state and call metadata (D29)."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    choices = {'throne': {'where': 'festival_grounds', 'spot': 'the raspberry thicket',
                         'aim': 'Secretly follow Tam without being seen.',
                         'intent': 'Catch the thief in the act'}}
    adjudicate = _adjudicate_reply({
        'throne': _settled('festival_grounds', 'Throné finds nothing unusual.',
                           spot='the raspberry thicket'),
    })
    offscreen = _offscreen_reply(state)
    (_events, _updated, _notes, _encounters, _statuses), requests = _run_resolve(
        world, run, monkeypatch, state, choices, [adjudicate, offscreen])
    assert len(requests) == 2
    offscreen_request = json.loads(requests[1])
    assert set(offscreen_request) == {'call', 'reply', 'clock', 'places', 'people', 'situations'}
    assert 'Throné finds nothing unusual.' not in requests[1]
    assert all('touches' not in item for item in offscreen_request['situations'])
    assert 'Secretly follow Tam' not in requests[1]
    assert 'Catch the thief' not in requests[1]


def test_offscreen_reply_omitting_people_keeps_them(tmp_path, monkeypatch):
    """People persist (D21): an offscreen reply that leaves someone out doesn't erase them."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    state.people['Gus'] = Person(where='festival_grounds', wants=['Save the contest'], commitments=[])
    reply = dict(call='offscreen', events=[], people={},
                situations=[situation.model_dump(include={"id", "status", "next", "due", "people"}) for situation in state.situations],
                places=[place.model_dump() for place in state.places],
                situation_notes={s.id: 'Unchanged.' for s in state.situations})
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', _fake_client(iter([json.dumps(reply)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.OffscreenAgent(ROOT, run, world, models.world,
                                             settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.offscreen(state, {s.id for s in state.situations if s.status == 'open'})

    _events, updated, _notes = asyncio.run(exercise())
    assert updated.people['Gus'].wants == ['Save the contest']


def test_encounter_mains_at_different_spots_rejected(tmp_path, monkeypatch):
    """An encounter's main characters must share one verdict place and spot; listing two
    whose verdicts don't is rejected and retried."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    bad = _adjudicate_reply({
        'agnea': _settled('festival_grounds', 'Agnea waits by the stage.', spot='by the stage'),
        'throne': _settled('festival_grounds', 'Throné waits by the stalls.', spot='by the stalls'),
    }, encounters=[{'mains': ['agnea', 'throne'], 'minor': []}])
    good = _adjudicate_reply({
        'agnea': _settled('festival_grounds', 'Agnea waits by the stage.', spot='by the stage'),
        'throne': _settled('festival_grounds', 'Throné joins her by the stage.', spot='by the stage'),
    }, encounters=[{'mains': ['agnea', 'throne'], 'minor': []}])
    offscreen = _offscreen_reply(state)
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient',
                        _fake_client(iter([json.dumps(bad), json.dumps(good), json.dumps(offscreen)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            async with world_agent.OffscreenAgent(ROOT, run, world, models.world,
                                                  settings.agent_max_turns, TraceWriter(run)) as offscreen:
                return await agent.resolve(state, {'agnea': {}, 'throne': {}}, [], offscreen=offscreen)

    _events, updated, _notes, encounters, _statuses = asyncio.run(exercise())
    assert len(requests) == 3
    assert updated.characters['agnea'].spot == updated.characters['throne'].spot == 'by the stage'
    assert encounters[0].mains == ['agnea', 'throne']
    failures = [row for row in map(json.loads, (run / 'trace.jsonl').read_text().splitlines())
               if row['type'] == 'world_validation_failed']
    assert len(failures) == 1 and 'share one place and spot' in failures[0]['error']
    assert 'agnea' in failures[0]['error'] and 'throne' in failures[0]['error']


def test_world_of_scene_round_accepted_for_previous_winner(tmp_path, monkeypatch):
    """A scene_round outcome may set `of` to the previous round's winner, a main character."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor='world', of='throne', type='world',
                 content='Throné tracks Tam and finds him near the stalls.', perceived_by=['agnea'])
    reply = dict(call='scene_round', outcome=event, minor_moves={})
    result, requests = _run_round(world, run, monkeypatch, state,
                                  {'actor': 'throne', 'move': 'act'}, reply)
    outcome, _minor_moves, _state = result
    assert len(requests) == 1
    assert outcome.of == 'throne'


def test_round_rejects_minor_move_without_known_person(tmp_path, monkeypatch):
    """A minor_moves name that is neither an existing people entry here nor in new_people is rejected and retried."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    bad = dict(call='scene_round', outcome=None,
              minor_moves={'Mystery': dict(move='act', urge=1, to=None, action='Waves.', say='Hello!')})
    good = dict(call='scene_round', outcome=None, minor_moves={})
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient',
                        _fake_client(iter([json.dumps(bad), json.dumps(good)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.round(state, [], place='festival_grounds',
                                     main_present=['agnea', 'throne'], minor_present=[],
                                     last_winner=None)

    outcome, minor_moves, result_state = asyncio.run(exercise())
    assert outcome is None and minor_moves == {}
    assert result_state == state
    assert len(requests) == 2
    failures = [row for row in map(json.loads, (run / 'trace.jsonl').read_text().splitlines())
                if row['type'] == 'world_validation_failed']
    assert len(failures) == 1
    assert 'Mystery' in failures[0]['error']
    assert load_state(world) == state


def test_round_new_people_entry_persists_to_state_json(tmp_path, monkeypatch):
    """A minor who joins with a new_people entry is added to the world's people and saved."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    reply = dict(call='scene_round', outcome=None,
                minor_moves={'Gus': dict(move='act', urge=1, to=None, action='Waves.', say='Hello!')},
                new_people={'Gus': dict(where='festival_grounds', wants=['Catch up with Agnea'], commitments=[])})
    result, requests = _run_round(world, run, monkeypatch, state, None, reply)
    outcome, minor_moves, result_state = result
    assert len(requests) == 1
    assert 'Gus' in minor_moves
    assert result_state.people['Gus'].where == 'festival_grounds'
    saved = load_state(world)
    assert saved.people['Gus'].where == 'festival_grounds'
    assert saved.people['Gus'].wants == ['Catch up with Agnea']


def test_round_request_includes_present_minor_people_entries(tmp_path, monkeypatch):
    """The scene-round request carries the people entries of the minor participants present."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    state.people['Tam'] = Person(where='festival_grounds', wants=['Find a quiet corner'], commitments=[])
    save_state(world, state)
    state = load_state(world)
    reply = dict(call='scene_round', outcome=None, minor_moves={})
    result, requests = _run_round(world, run, monkeypatch, state, None, reply)
    assert len(requests) == 1
    request = json.loads(requests[0])
    assert request['people'] == {'Tam': {'where': 'festival_grounds', 'spot': None,
                                         'wants': ['Find a quiet corner'], 'commitments': []}}


def test_world_of_scene_round_rejects_non_winner(tmp_path, monkeypatch):
    """`of` naming a main character who was not the previous round's winner is rejected."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    event = dict(place='festival_grounds', actor='world', of='throne', type='world',
                 content='Throné tracks Tam and finds him near the stalls.', perceived_by=['agnea'])
    reply = dict(call='scene_round', outcome=event, minor_moves={})
    requests = []
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient',
                        _fake_client(iter([json.dumps(reply), json.dumps(reply)]), requests))
    models, settings = load_configs()

    async def exercise():
        async with world_agent.WorldAgent(ROOT, run, world, models.world,
                                         settings.agent_max_turns, TraceWriter(run)) as agent:
            return await agent.round(state, [], place='festival_grounds',
                                     main_present=['agnea', 'throne'], minor_present=['Tam'],
                                     last_winner={'actor': 'agnea', 'move': 'act'})

    with pytest.raises(world_agent.SessionError, match='World event of must name'):
        asyncio.run(exercise())


def test_round_matches_people_names_ignoring_case(tmp_path, monkeypatch):
    """People are data references: 'Garud' in minor_moves resolves to the `garud` entry."""
    from story_engine.world.models import Person
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    state.people['garud'] = Person(where='festival_grounds', wants=['Watch his daughter dance'], commitments=[])
    reply = dict(call='scene_round', outcome=None,
                 minor_moves={'Garud': dict(move='wait', urge=0, to=None, action='', say='')})
    (outcome, minor_moves, _state), _requests = _run_round(world, run, monkeypatch, state, None, reply)
    assert list(minor_moves) == ['garud']
