import asyncio
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from story_engine.agents import character, world as world_agent
from story_engine.simulation import TickSession, run_scene, run_tick
from story_engine.world.io import read_events, read_scenes
from story_engine.world.models import Person

ROOT = Path(__file__).resolve().parents[2]


def move(kind='act', urge=2, to=None, action='Waves.', say='Hello.'):
    return dict(call='action', intent='Meet the others', move=kind, urge=urge, to=to,
                action=action, say=say)


def plan(where='festival_grounds', spot=None, aim='Enjoy the festival.'):
    return dict(call='plan', intent='Meet the others', where=where, spot=spot, aim=aim)


def world_state_echo(request):
    return {k: v for k, v in request['state'].items() if k != 'clock'}


def settled_verdicts(state_echo, outcome='Nothing much happens.'):
    """Settle every planning character right where it already stood (no movement)."""
    return {slug: dict(involves=[], status='settled', outcome=outcome, where=char['where'], spot=char.get('spot'))
           for slug, char in state_echo['characters'].items()}


def offscreen_echo(request):
    """A trivial offscreen reply that changes nothing: echoes places/situations, no events."""
    request = request['state']
    return dict(call='offscreen', events=[], people={},
               situations=[{key: item[key] for key in ('id', 'status', 'next', 'due', 'people')}
                           for item in request['situations']], places=request['places'],
               situation_notes={s['id']: 'Unchanged.' for s in request['situations']})


@pytest.mark.parametrize('case', ['addressee', 'display_name', 'interrupt', 'equal_three', 'tie', 'leave', 'dispersed', 'quiet', 'cap'])
def test_scene_fake_sdk(tmp_path, monkeypatch, case):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    requests = []

    class FakeClient:
        def __init__(self, *, options):
            self.is_world = options.system_prompt.startswith('# World')
            self.slug = None
            # TickSession opens characters in world order.
            if not self.is_world:
                self.slug = next(slugs)
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            try:
                self.request = json.loads(request)
            except json.JSONDecodeError:
                self.request = {}
            requests.append((self.slug, self.request))

        async def receive_response(self):
            if self.is_world:
                if self.request['call'] == 'adjudicate':
                    state_echo = world_state_echo(self.request)
                    data = dict(call='adjudicate', verdicts=settled_verdicts(state_echo), encounters=[])
                elif self.request['call'] == 'offscreen':
                    data = offscreen_echo(self.request)
                else:
                    data = dict(call='scene_round', outcome=None, minor_moves={})
            elif self.request.get('call') == 'part_of_day':
                data = plan()
            else:
                self.round += 1
                r, slug = self.round, self.slug
                if case == 'quiet' or (case not in ('cap', 'leave', 'dispersed') and r > 2):
                    data = move('wait', 0, action='Looks on.', say='Ignored wait speech')
                elif case in ('leave', 'dispersed'):
                    data = move('leave', 0) if slug == 'throne' or case == 'dispersed' else move()
                elif case == 'display_name':
                    data = move(urge=3 if r == 1 and slug == 'agnea' else 2,
                                to='Throné' if r == 1 and slug == 'agnea' else None)
                elif r == 1 and case in ('addressee', 'interrupt', 'equal_three'):
                    data = move(urge=3 if slug == 'agnea' else 1, to='throne')
                elif r == 2 and case in ('addressee', 'interrupt', 'equal_three'):
                    data = move(urge=(3 if case in ('interrupt', 'equal_three') else 2)
                                if slug == 'agnea' else (3 if case == 'equal_three' else 1))
                else:
                    data = move()
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    slugs = iter(['agnea', 'throne'])
    monkeypatch.setattr(character, 'ClaudeSDKClient', FakeClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', FakeClient)

    async def exercise():
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 5
            return await run_tick(world, run, session=session)

    state = asyncio.run(exercise())
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    rounds = [row for row in trace if row['type'] == 'scene_round']
    end = next(row for row in trace if row['type'] == 'scene_ended')
    assert all(row['place'] == 'festival_grounds' for row in rounds)
    assert state.clock.part == 'afternoon'
    assert all(event.part == 'morning' and event.scene is None
              for event in read_events(world) if event.actor in ('agnea', 'throne')
              and event.id <= 2)
    if case == 'display_name':
        assert rounds[0]['winner'] == 'agnea'
        assert rounds[0]['moves']['agnea']['to'] == 'Throné'
        assert all(action['urge'] == 2 for action in rounds[1]['moves'].values())
        assert rounds[1]['winner'] == 'throne' and rounds[1]['floor'] == 'addressee'
    elif case in ('addressee', 'equal_three'):
        assert rounds[1]['winner'] == 'throne' and rounds[1]['floor'] == 'addressee'
    elif case == 'interrupt':
        assert rounds[1]['winner'] == 'agnea' and rounds[1]['floor'] == 'interrupt'
    elif case == 'tie':
        assert [row['winner'] for row in rounds[:2]] == ['agnea', 'throne']
    elif case == 'leave':
        assert end['reason'] == 'one_left' and end['rounds'] == 1
        assert any(event.actor == 'throne' and 'leaves.' in event.content for event in read_events(world))
    elif case == 'dispersed':
        assert end['reason'] == 'no_main' and end['rounds'] == 1
    elif case == 'quiet':
        assert end['reason'] == 'quiet' and end['rounds'] == 2
        assert all(event.content != 'Ignored wait speech' for event in read_events(world))
    else:
        assert end['reason'] == 'part_over' and end['rounds'] == len(rounds) == 5
    # Calls within a round see the identical pre-round event snapshot, aside from each
    # character's own private plan (perceived only by its maker, never shared).
    scene_requests = [(slug, req) for slug, req in requests if slug and 'part' not in req]

    def shared(req):
        return [e for e in req['perceived'] if e['type'] != 'plan']

    for (_, first), (_, second) in zip(scene_requests[::2], scene_requests[1::2]):
        assert shared(first) == shared(second)
    if case == 'tie':
        note = next(req['note'] for slug, req in scene_requests if slug == 'throne' and 'note' in req)
        assert "didn't happen" in note and 'agnea' in note
    # Each round's World call carries the previous round's winner, not this round's choices.
    resolutions = [req for slug, req in requests if slug is None and req.get('call') == 'scene_round']
    assert resolutions[0]['last_winner'] is None
    for prior, resolution in zip(rounds, resolutions[1:]):
        if prior['winner']:
            assert resolution['last_winner']['actor'] == prior['winner']
        else:
            assert resolution['last_winner'] is None


def test_minor_joins_by_address_and_wins_floor(tmp_path, monkeypatch):
    """A main character addresses an absent minor by name; next round the minor wins the floor."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    requests = []
    slugs = iter(['agnea', 'throne'])

    class CharClient:
        def __init__(self, *, options):
            self.slug = next(slugs)
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)
            requests.append((self.slug, self.request))

        async def receive_response(self):
            self.round += 1
            if self.slug == 'agnea' and self.round == 1:
                data = move(urge=2, to='Gus', say='Hey Gus!')
            else:
                data = move('wait', 0, action='', say='')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)
            requests.append((None, self.request))

        async def receive_response(self):
            self.round += 1
            if self.round == 1:
                data = dict(call='scene_round', outcome=None, minor_moves={})
            else:
                data = dict(call='scene_round', outcome=None, minor_moves={
                    'Gus': dict(move='act', urge=1, to=None, action='Waves back.', say='There you are!')},
                    new_people={'Gus': dict(where='festival_grounds', wants=['Greet old friends'], commitments=[])})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    from story_engine.world.io import load_state

    async def exercise():
        state = load_state(world)
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 4
            return await run_scene(world, session, state, 'festival_grounds', ['agnea', 'throne'], [])

    asyncio.run(exercise())
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    rounds = [row for row in trace if row['type'] == 'scene_round']
    assert rounds[0]['winner'] == 'agnea'
    assert rounds[1]['winner'] == 'Gus' and rounds[1]['floor'] == 'addressee'
    assert any(event.actor == 'Gus' and event.intent is None for event in read_events(world))


def test_minor_visible_wait_not_logged_but_floor_win_is(tmp_path, monkeypatch):
    """A minor's visible wait is never logged (D25: no audience); a round the minor wins is."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    slugs = iter(['agnea', 'throne'])

    class CharClient:
        def __init__(self, *, options):
            self.slug = next(slugs)
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            self.round += 1
            data = move('wait', 0, action='', say='')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            self.round += 1
            if self.round == 1:
                data = dict(call='scene_round', outcome=None, minor_moves={
                    'Gus': dict(move='wait', urge=0, to=None, action='Watches from the stall.', say='')})
            else:
                data = dict(call='scene_round', outcome=None, minor_moves={
                    'Gus': dict(move='act', urge=1, to=None, action='Waves.', say='Hello there!')})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    from story_engine.world.io import load_state

    async def exercise():
        state = load_state(world)
        state.people['Gus'] = Person(where='festival_grounds', wants=['Mind the stall'], commitments=[])
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 2
            return await run_scene(world, session, state, 'festival_grounds', ['agnea', 'throne'], ['Gus'])

    asyncio.run(exercise())
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    rounds = [row for row in trace if row['type'] == 'scene_round']
    assert rounds[1]['winner'] == 'Gus'
    gus_events = [event for event in read_events(world) if event.actor == 'Gus']
    assert len(gus_events) == 1
    assert gus_events[0].content == 'Waves. Hello there!'
    assert 'Watches from the stall.' not in [event.content for event in read_events(world)]


def test_unresolved_addressee_adds_no_phantom_participant(tmp_path, monkeypatch):
    """`to: "everyone"` never resolves to a participant; a leaving main character still ends the scene."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    slugs = iter(['agnea', 'throne'])

    class CharClient:
        def __init__(self, *, options):
            self.slug = next(slugs)
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            self.round += 1
            if self.slug == 'agnea':
                data = move(to='everyone') if self.round == 1 else move('wait', 0, action='', say='')
            else:
                data = move('wait', 0, action='', say='') if self.round == 1 else move('leave', 0)
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)

        async def receive_response(self):
            # The World never brings in a minor here: "everyone"/"the crowd" is never a real person.
            data = dict(call='scene_round', outcome=None, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    from story_engine.world.io import load_state

    async def exercise():
        state = load_state(world)
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 5
            return await run_scene(world, session, state, 'festival_grounds', ['agnea', 'throne'], [])

    asyncio.run(exercise())
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    end = next(row for row in trace if row['type'] == 'scene_ended')
    assert end['reason'] == 'one_left' and end['rounds'] == 2
    rounds = [row for row in trace if row['type'] == 'scene_round']
    assert all(set(row['moves']) <= {'agnea', 'throne'} for row in rounds)
    scenes = read_scenes(world)
    assert len(scenes) == 1 and set(scenes[0].participants) == {'agnea', 'throne'}


def test_round_rejects_extra_events_and_caps_logged_events(tmp_path, monkeypatch):
    """A reply with more than one outcome event is rejected and retried, not appended whole."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    slugs = iter(['agnea', 'throne'])

    class CharClient:
        def __init__(self, *, options):
            self.slug = next(slugs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            data = move() if self.slug == 'agnea' else move('wait', 0, action='Nods.', say='')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            self.attempt = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            self.attempt += 1
            event = dict(place='festival_grounds', actor='world', type='world',
                        content='A breeze passes.', perceived_by=['agnea', 'throne'])
            if self.attempt == 1:
                # Extra 'events' alongside a single outcome: must be rejected, not appended.
                data = dict(call='scene_round', outcome=event, minor_moves={}, events=[event, event])
            else:
                data = dict(call='scene_round', outcome=event, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    from story_engine.world.io import load_state

    async def exercise():
        state = load_state(world)
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 1
            return await run_scene(world, session, state, 'festival_grounds', ['agnea', 'throne'], [])

    asyncio.run(exercise())
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    failures = [row for row in trace if row['type'] == 'world_validation_failed']
    assert len(failures) == 1
    scene_events = [event for event in read_events(world) if event.scene is not None]
    # At most: the floor winner (agnea), one visible wait (throne), and one outcome event.
    assert len(scene_events) <= 3


def test_scene_events_carry_round_and_outcome_resolves_previous_round(tmp_path, monkeypatch):
    """Scene events get the round they happened in; an outcome event gets the round of the
    move it resolves (the previous round), not the round it was produced in."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    slugs = iter(['agnea', 'throne'])

    class CharClient:
        def __init__(self, *, options):
            self.slug = next(slugs)
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            self.round += 1
            if self.round == 1:
                data = (move(urge=2, action='Waves.', say='Hello.') if self.slug == 'agnea'
                       else move('wait', 0, action='Looks on.', say=''))
            else:
                data = (move('wait', 0, action='', say='') if self.slug == 'agnea'
                       else move('leave', 0, action='', say=''))
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            self.round += 1
            if self.round == 1:
                data = dict(call='scene_round', outcome=None, minor_moves={})
            else:
                outcome = dict(place='festival_grounds', actor='world', of='agnea',
                               type='world', content="Agnea's wave is seen.", perceived_by=['agnea', 'throne'])
                data = dict(call='scene_round', outcome=outcome, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    from story_engine.world.io import load_state

    async def exercise():
        state = load_state(world)
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 2
            return await run_scene(world, session, state, 'festival_grounds', ['agnea', 'throne'], [])

    asyncio.run(exercise())
    rounds_by_content = {event.content: event.round for event in read_events(world) if event.scene is not None}
    assert rounds_by_content['Waves. Hello.'] == 1
    assert rounds_by_content['Looks on.'] == 1
    outcome_event = next(event for event in read_events(world) if event.actor == 'world')
    assert outcome_event.round == 1  # resolves round 1's winning move, even though produced in round 2
    leave_event = next(event for event in read_events(world) if 'leaves.' in event.content)
    assert leave_event.round == 2


def test_scene_recorded_in_scenes_jsonl(tmp_path, monkeypatch):
    """Two main characters meet even with no encounter listed; the scene and its events are tagged."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    slugs = iter(['agnea', 'throne'])

    class CharClient:
        def __init__(self, *, options):
            self.is_char = True
            self.slug = next(slugs)
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)

        async def receive_response(self):
            if self.request.get('call') == 'part_of_day':
                data = plan()
            else:
                self.round += 1
                data = move('wait', 0, action='', say='') if self.round > 1 else move('wait', 0, action='Looks around.', say='')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def __init__(self, *, options):
            pass

        async def query(self, request):
            self.request = json.loads(request)

        async def receive_response(self):
            if self.request['call'] == 'adjudicate':
                state_echo = world_state_echo(self.request)
                data = dict(call='adjudicate', verdicts=settled_verdicts(state_echo), encounters=[])
            elif self.request['call'] == 'offscreen':
                data = offscreen_echo(self.request)
            else:
                data = dict(call='scene_round', outcome=None, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    async def exercise():
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 5
            return await run_tick(world, run, session=session)

    asyncio.run(exercise())
    scenes = read_scenes(world)
    assert len(scenes) == 1
    scene = scenes[0]
    events = read_events(world)
    part_of_day_events = [e for e in events if e.id < scene.first_event_id or e.id > scene.last_event_id]
    scene_events = [e for e in events if scene.first_event_id <= e.id <= scene.last_event_id]
    assert part_of_day_events and all(e.scene is None for e in part_of_day_events)
    assert scene_events and all(e.scene == scene.id for e in scene_events)
    assert set(scene.participants) == {'agnea', 'throne'}


def test_solo_main_with_listed_minor_runs_scene(tmp_path, monkeypatch):
    """A single main character plus a World-listed minor encounter still runs a scene."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    slugs = iter(['agnea', 'throne'])

    class CharClient:
        def __init__(self, *, options):
            self.slug = next(slugs)
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)

        async def receive_response(self):
            if self.request.get('call') == 'part_of_day':
                where = 'festival_grounds' if self.slug == 'agnea' else 'cropdale'
                data = plan(where=where, aim=f'Head to {where}.')
            else:
                self.round += 1
                data = move('wait', 0, action='', say='')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)

        async def receive_response(self):
            if self.request['call'] == 'adjudicate':
                verdicts = dict(
                    agnea=dict(involves=[], status='settled', outcome='Agnea reaches the festival grounds.',
                              where='festival_grounds', spot=None),
                    throne=dict(involves=[], status='settled', outcome='Throné reaches Cropdale.',
                               where='cropdale', spot=None))
                data = dict(call='adjudicate', verdicts=verdicts,
                           encounters=[{'mains': ['agnea'], 'minor': ['Gus']}])
            elif self.request['call'] == 'offscreen':
                data = offscreen_echo(self.request)
            else:
                data = dict(call='scene_round', outcome=None, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    async def exercise():
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 3
            return await run_tick(world, run, session=session)

    asyncio.run(exercise())
    scenes = read_scenes(world)
    assert len(scenes) == 1
    assert scenes[0].place == 'festival_grounds'
    assert set(scenes[0].participants) == {'agnea', 'Gus'}


def test_round_reply_with_state_key_is_rejected(tmp_path, monkeypatch):
    """A scene_round reply may not carry a `state` key at all; it is a scene round no longer carries state."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    slugs = iter(['agnea', 'throne'])

    class CharClient:
        def __init__(self, *, options):
            self.slug = next(slugs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            yield ResultMessage('success', 1, 1, False, 1, 'fake',
                               result=json.dumps(move('wait', 0, action='', say='')))

    class WorldClient:
        def __init__(self, *, options):
            self.attempt = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            try:
                self.request = json.loads(request)
            except json.JSONDecodeError:
                pass

        async def receive_response(self):
            self.attempt += 1
            if self.attempt == 1:
                # Carrying a `state` key at all is rejected, even when it matches the input exactly.
                data = dict(call='scene_round', outcome=None, minor_moves={},
                           state=world_state_echo(self.request))
            else:
                data = dict(call='scene_round', outcome=None, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    from story_engine.world.io import load_state

    async def exercise():
        state = load_state(world)
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 1
            return await run_scene(world, session, state, 'festival_grounds', ['agnea', 'throne'], [])

    asyncio.run(exercise())
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    failures = [row for row in trace if row['type'] == 'world_validation_failed']
    assert len(failures) == 1
    assert 'state' in failures[0]['error'].lower() or 'extra' in failures[0]['error'].lower()


def test_scene_leaves_state_json_byte_identical(tmp_path, monkeypatch):
    """A whole fake scene never writes state.json; its bytes are unchanged before and after."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    slugs = iter(['agnea', 'throne'])
    before = (world / 'state.json').read_bytes()

    class CharClient:
        def __init__(self, *, options):
            self.slug = next(slugs)
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            self.round += 1
            data = move('leave', 0) if self.round == 1 and self.slug == 'throne' else move()
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            data = dict(call='scene_round', outcome=None, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    from story_engine.world.io import load_state

    async def exercise():
        state = load_state(world)
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 5
            return await run_scene(world, session, state, 'festival_grounds', ['agnea', 'throne'], [])

    asyncio.run(exercise())
    assert (world / 'state.json').read_bytes() == before


def test_solo_attempt_scene_ends_on_quiet_not_participant_count(tmp_path, monkeypatch):
    """A one-character attempt scene (D26) never ends for having fewer than two
    participants; it ends only when the character leaves, after two quiet rounds, or at cap."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()

    class CharClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            data = move('wait', 0, action='', say='')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            data = dict(call='scene_round', outcome=None, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    from story_engine.world.io import load_state

    async def exercise():
        state = load_state(world)
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 5
            return await run_scene(world, session, state, 'festival_grounds', ['throne'], [])

    asyncio.run(exercise())
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    end = next(row for row in trace if row['type'] == 'scene_ended')
    # Never ends at round 1 merely for being alone; only after two quiet rounds.
    assert end['reason'] == 'quiet' and end['rounds'] == 2
    scenes = read_scenes(world)
    assert len(scenes) == 1 and scenes[0].participants == ['throne']


def test_solo_attempt_scene_ends_when_character_leaves(tmp_path, monkeypatch):
    """A one-character attempt scene ends as soon as that character leaves, even at round 1."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()

    class CharClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            data = move('leave', 0)
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            pass

        async def receive_response(self):
            data = dict(call='scene_round', outcome=None, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    from story_engine.world.io import load_state

    async def exercise():
        state = load_state(world)
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 5
            return await run_scene(world, session, state, 'festival_grounds', ['throne'], [])

    asyncio.run(exercise())
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    end = next(row for row in trace if row['type'] == 'scene_ended')
    assert end['reason'] == 'no_main' and end['rounds'] == 1


def test_two_mains_same_place_different_spots_no_scene_same_spot_opens_one(tmp_path, monkeypatch):
    """Two main characters sharing a place but not a spot never meet (D26); sharing both
    place and spot, they always open a scene."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    slugs = iter(['agnea', 'throne'])

    class CharClient:
        def __init__(self, *, options):
            self.slug = next(slugs)
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)

        async def receive_response(self):
            if self.request.get('call') == 'part_of_day':
                data = plan(where='cropdale', spot=same_spot.get(self.slug))
            else:
                self.round += 1
                data = move('wait', 0, action='', say='')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)

        async def receive_response(self):
            if self.request['call'] == 'adjudicate':
                verdicts = {slug: dict(involves=[], status='settled', outcome='Nothing much happens.',
                                       where='cropdale', spot=same_spot.get(slug))
                           for slug in self.request['choices']}
                data = dict(call='adjudicate', verdicts=verdicts, encounters=[])
            elif self.request['call'] == 'offscreen':
                data = offscreen_echo(self.request)
            else:
                data = dict(call='scene_round', outcome=None, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    async def exercise():
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 3
            return await run_tick(world, run, session=session)

    same_spot = {'agnea': 'the tavern bar', 'throne': 'the orchard gate'}
    slugs = iter(['agnea', 'throne'])
    asyncio.run(exercise())
    assert read_scenes(world) == []

    world2, run2 = world.parent / 'world2', run.parent / 'run2'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world2)
    run2.mkdir()
    same_spot = {'agnea': 'the tavern bar', 'throne': 'the tavern bar'}
    slugs = iter(['agnea', 'throne'])

    async def exercise2():
        async with TickSession(world2, run2, root=ROOT) as session:
            session.settings.scene_cap = 3
            return await run_tick(world2, run2, session=session)

    asyncio.run(exercise2())
    scenes = read_scenes(world2)
    assert len(scenes) == 1 and set(scenes[0].participants) == {'agnea', 'throne'}
    assert scenes[0].spot == 'the tavern bar'


def test_encounter_scene_opens_at_mains_shared_spot(tmp_path, monkeypatch):
    """A listed encounter's scene opens wherever its `mains` actually ended up (D26 fix):
    the World no longer names a place/spot on the encounter itself."""
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    slugs = iter(['agnea', 'throne'])

    class CharClient:
        def __init__(self, *, options):
            self.slug = next(slugs)
            self.round = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)

        async def receive_response(self):
            if self.request.get('call') == 'part_of_day':
                data = (plan(where='festival_grounds', spot='the raspberry thicket', aim='Search the thicket.')
                       if self.slug == 'agnea' else plan(where='cropdale', aim='Mind the tavern.'))
            else:
                self.round += 1
                data = move('wait', 0, action='', say='')
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    class WorldClient:
        def __init__(self, *, options):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)

        async def receive_response(self):
            if self.request['call'] == 'adjudicate':
                verdicts = dict(
                    agnea=dict(involves=[], status='staged', where='festival_grounds', spot='the raspberry thicket'),
                    throne=dict(involves=[], status='settled', outcome='Throné minds the tavern.',
                               where='cropdale', spot=None))
                data = dict(call='adjudicate', verdicts=verdicts,
                           encounters=[{'mains': ['agnea'], 'minor': []}])
            elif self.request['call'] == 'offscreen':
                data = offscreen_echo(self.request)
            else:
                data = dict(call='scene_round', outcome=None, minor_moves={})
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=json.dumps(data))

    monkeypatch.setattr(character, 'ClaudeSDKClient', CharClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', WorldClient)

    async def exercise():
        async with TickSession(world, run, root=ROOT) as session:
            session.settings.scene_cap = 3
            return await run_tick(world, run, session=session)

    asyncio.run(exercise())
    scenes = read_scenes(world)
    assert len(scenes) == 1
    assert scenes[0].place == 'festival_grounds' and scenes[0].spot == 'the raspberry thicket'
    assert scenes[0].participants == ['agnea']
