"""D29 day renewal and off-screen isolation, using only fake SDK clients."""

import asyncio
import copy
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from pydantic import ValidationError

from story_engine import simulation
from story_engine.agents import character, world as world_agent
from story_engine.agents.sdk import SessionError
from story_engine.config import load_configs
from story_engine.trace import TraceWriter
from story_engine.world.io import append_event, load_state, read_events, save_state
from story_engine.world.models import Event

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def workspace(tmp_path):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    return world, run


def fake_sdk(monkeypatch, respond):
    clients = []

    class Client:
        def __init__(self, *, options):
            self.options, self.calls, self.closed = options, [], False
            clients.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            self.closed = True

        async def query(self, request):
            try:
                self.request = json.loads(request)
            except ValueError:
                self.request = request  # validation feedback on the same client
            self.calls.append(self.request)

        async def receive_response(self):
            reply = respond(self, self.request)
            yield ResultMessage('success', 1, 1, False, 1, 'fake',
                                structured_output=reply, total_cost_usd=.01 * len(self.calls))

    monkeypatch.setattr(character, 'ClaudeSDKClient', Client)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', Client)
    return clients


def agent(agent_type, world, run):
    models, settings = load_configs(ROOT / 'config/models.yaml')
    return agent_type(ROOT, run, world, models.world, settings.agent_max_turns, TraceWriter(run))


def situation(id='new-promise', kind='promise', part='evening'):
    return dict(id=id, kind=kind, summary='A supper invitation.', touches=['agnea'],
                people=[], status='open', next='The supper starts.', due=dict(day=2, part=part))


def failures(run):
    return [row for row in map(json.loads, (run / 'trace.jsonl').read_text().splitlines())
            if row['type'] == 'world_validation_failed']


@pytest.mark.parametrize('day', [1, 2, 3])
def test_run_day_first_calls_goals_and_visible_history(workspace, monkeypatch, day):
    world, run = workspace
    # Keep the legacy state format (no people, spots, or kind on some situations).
    raw = json.loads((world / 'state.json').read_text())
    raw['clock']['day'] = day
    (world / 'state.json').write_text(json.dumps(raw))
    old_state = load_state(world)
    memory_bytes = b'Previous memory\r\nThe festival is over.\r\n'
    for slug in old_state.characters:
        (world / 'memory' / f'{slug}.md').write_bytes(memory_bytes)
    for event_day, event_type, content in [
        (day - 2, 'action', 'Older visible event'),
        (day - 1, 'action', 'Yesterday visible event'),
        (day - 1, 'plan', 'Yesterday private plan'),
        (day, 'action', 'Current day event'),
    ]:
        append_event(world, Event(id=0, day=event_day, part='night', place='cropdale',
                                 actor='agnea', type=event_type, content=content,
                                 intent='Private intent', perceived_by=['agnea']))
    call_order = []
    new_situation = situation()
    new_situation['due']['day'] = day

    def respond(client, request):
        call_order.append(request['call'])
        is_world = client.options.system_prompt.startswith('# World')
        if request['call'] == 'day_start':
            assert len(client.calls) == 1
            assert request['reply']
            if is_world:
                assert all(c.goals == ['Make a new plan'] for c in load_state(world).characters.values())
                assert request['state'] == load_state(world).model_dump()
                assert [e['content'] for e in request['events']] == ['Yesterday visible event']
                assert all('intent' not in e and e['type'] != 'plan' for e in request['events'])
                return dict(call='day_start', situations=[new_situation])
            assert 'The festival is over.' in request['memory']
            return dict(call='day_start', goals=['Make a new plan'])
        assert request['call'] == 'end_of_day'
        return dict(call='end_of_day', summary='New memory')

    clients = fake_sdk(monkeypatch, respond)
    tick_calls = []
    original_session = simulation.TickSession
    monkeypatch.setattr(simulation, 'TickSession',
                        lambda w, r: original_session(w, r, root=ROOT))

    async def tick(world_dir, run_dir, *, session):
        state = load_state(world_dir)
        tick_calls.append(state)
        if day >= 2:
            assert call_order == ['day_start'] * 3
            assert all(c.goals == ['Make a new plan'] for c in state.characters.values())
            assert state.situations[-1].id == 'new-promise'
        else:
            assert call_order == [] and state == old_state
        # Day start reads old memory but never rewrites it.
        assert (world / 'memory/agnea.md').read_bytes() == memory_bytes
        state.clock.day += 1
        save_state(world_dir, state)
        return state

    monkeypatch.setattr(simulation, 'run_tick', tick)
    result = asyncio.run(simulation.run_day(world, run))
    assert len(tick_calls) == 1 and result.clock.day == day + 1
    assert len(clients) == 4 and all(client.closed for client in clients)
    assert clients[3].calls == []  # merely opened alongside the other day sessions
    if day >= 2:
        assert all(client.calls[0]['call'] == 'day_start' for client in clients[:3])
        assert all(c.goals == ['Make a new plan'] for c in load_state(world).characters.values())
    else:
        assert all(request['call'] != 'day_start' for client in clients for request in client.calls)


def test_run_day_afternoon_resume_skips_day_start(workspace, monkeypatch):
    world, run = workspace
    state = load_state(world)
    state.clock.day, state.clock.part = 2, 'afternoon'
    save_state(world, state)

    def respond(client, request):
        assert request['call'] == 'end_of_day'
        return dict(call='end_of_day', summary='New memory')

    clients = fake_sdk(monkeypatch, respond)
    original_session = simulation.TickSession
    monkeypatch.setattr(simulation, 'TickSession',
                        lambda w, r: original_session(w, r, root=ROOT))
    parts = []

    async def tick(world_dir, run_dir, *, session):
        current = load_state(world_dir)
        assert current.characters == state.characters
        assert current.situations == state.situations
        parts.append(current.clock.part)
        index = session.settings.parts_of_day.index(current.clock.part) + 1
        current.clock.day += index == len(session.settings.parts_of_day)
        current.clock.part = session.settings.parts_of_day[index % len(session.settings.parts_of_day)]
        save_state(world_dir, current)
        return current

    monkeypatch.setattr(simulation, 'run_tick', tick)
    result = asyncio.run(simulation.run_day(world, run))
    assert parts == ['afternoon', 'evening', 'night']
    assert result.clock.day == 3
    assert all(request['call'] != 'day_start' for client in clients for request in client.calls)
    assert clients[2].calls == []  # World never receives day_start.


def test_run_day_first_tick_failure_restores_before_day_start(workspace, monkeypatch):
    world, run = workspace
    state = load_state(world)
    state.clock.day = 2
    save_state(world, state)
    before = (world / 'state.json').read_bytes()

    def respond(client, request):
        if request['call'] == 'day_start':
            assert len(client.calls) == 1
            if client.options.system_prompt.startswith('# World'):
                assert request['state']['situations'] == state.model_dump()['situations']
                return dict(call='day_start', situations=[situation()])
            return dict(call='day_start', goals=['Make a new plan'])
        assert request['call'] == 'end_of_day'
        return dict(call='end_of_day', summary='New memory')

    clients = fake_sdk(monkeypatch, respond)
    original_session = simulation.TickSession
    monkeypatch.setattr(simulation, 'TickSession',
                        lambda w, r: original_session(w, r, root=ROOT))
    fail = True

    async def tick(world_dir, run_dir, *, session):
        current = load_state(world_dir)
        assert current.clock.part == 'morning'
        assert all(c.goals == ['Make a new plan'] for c in current.characters.values())
        assert current.situations[:-1] == state.situations
        assert current.situations[-1].id == 'new-promise'
        if fail:
            raise RuntimeError('morning tick failed')
        current.clock.day += 1
        save_state(world_dir, current)
        return current

    monkeypatch.setattr(simulation, 'run_tick', tick)
    with pytest.raises(RuntimeError, match='morning tick failed'):
        asyncio.run(simulation.run_day(world, run))
    assert (world / 'state.json').read_bytes() == before
    assert load_state(world) == state
    failed = json.loads((run / 'world_failed/state.json').read_text())
    assert failed['situations'][-1]['id'] == 'new-promise'

    fail = False
    retry_run = run / 'retry'
    result = asyncio.run(simulation.run_day(world, retry_run))
    assert result.clock.day == 3
    assert len(clients) == 8 and all(client.closed for client in clients)
    for client in clients[:3] + clients[4:7]:
        assert sum(request['call'] == 'day_start' for request in client.calls) == 1


@pytest.mark.parametrize('bad,reason', [
    ('person', 'people must name'),
    ('touches', 'touches must name'),
    ('duplicate_existing', 'ids must be unique'),
    ('duplicate_new', 'ids must be unique'),
    ('kind', 'more than one kind'),
    ('due', 'same due part'),
    ('empty', 'at least 1'),
    ('too_many', 'at most 3'),
])
@pytest.mark.parametrize('correct_retry', [False, True])
def test_world_day_start_retries_once(workspace, monkeypatch, bad, reason, correct_retry):
    world, run = workspace
    state = load_state(world)
    good = dict(call='day_start', situations=[situation(), situation('occasion', 'occasion', 'night')])
    invalid = copy.deepcopy(good)
    first, second = invalid['situations']
    if bad == 'person':
        first['people'] = ['Unknown']
    elif bad == 'touches':
        first['touches'] = ['Minor']
    elif bad == 'duplicate_existing':
        first['id'] = state.situations[0].id
    elif bad == 'duplicate_new':
        second['id'] = first['id']
    elif bad == 'kind':
        second['kind'] = first['kind']
    elif bad == 'due':
        second['due'] = first['due']
    elif bad == 'empty':
        invalid['situations'] = []
    else:
        invalid['situations'] *= 2
    replies = iter([invalid, good if correct_retry else invalid])
    clients = fake_sdk(monkeypatch, lambda *_: next(replies))

    async def exercise():
        async with agent(world_agent.WorldAgent, world, run) as world_session:
            return await world_session.day_start(state, [])

    if correct_retry:
        result = asyncio.run(exercise())
        assert result == load_state(world)
        assert result.situations[:len(state.situations)] == state.situations
        assert [s.id for s in result.situations[-2:]] == ['new-promise', 'occasion']
    else:
        with pytest.raises(SessionError, match='after one retry'):
            asyncio.run(exercise())
        assert load_state(world) == state
    assert len(clients) == 1 and len(clients[0].calls) == 2
    assert reason in clients[0].calls[1]
    assert len(failures(run)) == (1 if correct_retry else 2)


def test_day_start_adds_people_and_places(workspace, monkeypatch):
    world, run = workspace
    state = load_state(world)
    new = situation()
    new['people'] = ['Host']
    reply = dict(call='day_start', situations=[new],
                 people={'Host': dict(where='new_place', wants=['Host supper'], commitments=[])},
                 places=[dict(slug='new_place', details=['A room'])])
    fake_sdk(monkeypatch, lambda *_: reply)

    async def exercise():
        async with agent(world_agent.WorldAgent, world, run) as world_session:
            return await world_session.day_start(state, [])

    result = asyncio.run(exercise())
    assert result == load_state(world)
    assert result.people['Host'].where == 'new_place'
    assert result.places[:-1] == state.places


@pytest.mark.parametrize('goals', [[], ['a', 'b', 'c', 'd']])
def test_character_day_start_goal_count_retries_once(workspace, monkeypatch, goals):
    world, run = workspace
    clients = fake_sdk(monkeypatch, lambda *_: dict(call='day_start', goals=goals))
    models, settings = load_configs()

    async def exercise():
        async with character.CharacterAgent(ROOT, run, world, 'agnea', models.character,
                                            settings.agent_max_turns, TraceWriter(run)) as session:
            await session.day_start()

    with pytest.raises(SessionError, match='after one retry'):
        asyncio.run(exercise())
    assert len(clients[0].calls) == 2


def test_offscreen_isolated_persistent_client_and_adjudicated_state(workspace, monkeypatch):
    world, run = workspace
    state = load_state(world)
    situation_id = state.situations[0].id
    (world / 'scene_context.md').write_text('PRIVATE SCENE CONTEXT')
    append_event(world, Event(id=0, day=1, part='morning', place='cropdale', actor='agnea',
                             type='plan', content='PRIVATE PLAN', intent='PRIVATE INTENT',
                             perceived_by=['agnea']))
    offscreen_requests = []

    def respond(client, request):
        assert request['reply']
        if request['call'] == 'adjudicate':
            return dict(call='adjudicate', verdicts={
                'agnea': dict(involves=[], status='settled', where='cropdale', outcome='PRIVATE OUTCOME')},
                situation_updates=[dict(id=situation_id, status='resolved')])
        if request['call'] == 'scene_round':
            return dict(call='scene_round', outcome=None, minor_moves={})
        assert request['call'] == 'offscreen'
        offscreen_requests.append(request)
        if len(offscreen_requests) == 1:
            assert set(request) == {'call', 'reply', 'state'}
            assert set(request['state']) == {'clock', 'places', 'people', 'situations'}
            assert request['state']['situations'][0]['status'] == 'resolved'
        else:
            assert set(request) == {'call', 'reply', 'state_changes'}
            assert request['state_changes'] == {}
        assert load_state(world).situations[0].status == 'resolved'
        # Assert keys recursively, not just at the request's top level.
        def keys(value):
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(v) for v in value))
            return set()
        assert not keys(request) & {'characters', 'outcomes', 'touches', 'intent', 'intents', 'events', 'choices'}
        for secret in ('PRIVATE PLAN', 'PRIVATE INTENT', 'PRIVATE OUTCOME', 'PRIVATE SCENE'):
            assert secret not in json.dumps(request) and secret not in client.options.system_prompt
        return dict(call='offscreen', places=[], situations=[],
                    situation_notes={s.id: 'Unchanged.' for s in load_state(world).situations
                                     if s.status == 'open'})

    clients = fake_sdk(monkeypatch, respond)

    async def exercise():
        async with simulation.TickSession(world, run, root=ROOT) as session:
            current = state
            for _ in range(2):
                _, current, _, _, _ = await session.world.resolve(
                    current, {'agnea': {'aim': 'PRIVATE PLAN', 'intent': 'PRIVATE INTENT'}},
                    read_events(world), offscreen=session.offscreen)
                await session.world.round(current, read_events(world), place='cropdale',
                                          main_present=['agnea'], minor_present=[],
                                          last_winner={'actor': 'agnea', 'intent': 'PRIVATE INTENT'})
            return current

    result = asyncio.run(exercise())
    assert result.situations[0].status == 'resolved'
    assert len(clients) == 4 and all(client.closed for client in clients)
    assert [r['call'] for r in clients[2].calls] == ['adjudicate', 'scene_round'] * 2
    assert clients[3].calls == offscreen_requests and len(offscreen_requests) == 2
    assert clients[2] is not clients[3]
    assert clients[3].options.system_prompt == (ROOT / 'prompts/world_offscreen.md').read_text()


@pytest.mark.parametrize('new_id', [True, False])
def test_offscreen_updates_only_existing_situations(workspace, monkeypatch, new_id):
    world, run = workspace
    state = load_state(world)
    update = dict(id='new' if new_id else state.situations[0].id, status='resolved',
                  next='Supper starts.', due=dict(day=2, part='night'), people=['Host'])
    reply = dict(call='offscreen', situations=[update],
                 people={'Host': dict(where='cropdale', wants=['Cook'], commitments=[])},
                 places=[p.model_dump() for p in state.places],
                 situation_notes={s.id: 'Updated.' for s in state.situations})
    clients = fake_sdk(monkeypatch, lambda *_: reply)

    async def exercise():
        async with agent(world_agent.OffscreenAgent, world, run) as session:
            return await session.offscreen(state, {s.id for s in state.situations})

    if new_id:
        with pytest.raises(SessionError, match='existing situation ids'):
            asyncio.run(exercise())
        assert len(clients[0].calls) == 2 and len(failures(run)) == 2
        assert load_state(world) == state
    else:
        _, result, _ = asyncio.run(exercise())
        assert result.situations[0].model_dump(include=set(update)) == update
        assert result.situations[0].touches == state.situations[0].touches
        assert result.situations[0].summary == state.situations[0].summary
        assert result.situations[0].kind == state.situations[0].kind
        assert result.situations[1:] == state.situations[1:]


@pytest.mark.parametrize('field,value', [('touches', ['agnea']), ('kind', 'wish'), ('summary', 'Changed')])
def test_offscreen_situation_schema_has_no_main_character_or_creation_fields(field, value):
    update = dict(id='existing', status='open', next='Wait.', due=dict(day=2, part='night'), people=[])
    with pytest.raises(ValidationError):
        world_agent.OffscreenReply.model_validate(dict(call='offscreen', situations=[{**update, field: value}]))


def test_offscreen_retry_does_not_echo_internal_state(workspace, monkeypatch):
    world, run = workspace
    state = load_state(world)
    state.characters['agnea'].goals = ['PRIVATE GOAL']
    invalid = dict(call='offscreen', places=[p.model_dump() for p in state.places],
                   situations=[dict(id=state.situations[0].id, status='open', next='Wait.',
                                    due=dict(day=2, part='night'), people=['Unknown'])],
                   situation_notes={s.id: 'Unchanged.' for s in state.situations})
    clients = fake_sdk(monkeypatch, lambda *_: invalid)

    async def exercise():
        async with agent(world_agent.OffscreenAgent, world, run) as session:
            await session.offscreen(state, {s.id for s in state.situations})

    with pytest.raises(SessionError, match='people must name'):
        asyncio.run(exercise())
    feedback = clients[0].calls[1]
    assert 'people must name' in feedback
    for forbidden in ('input_value', 'characters', 'touches', 'PRIVATE GOAL'):
        assert forbidden not in feedback
