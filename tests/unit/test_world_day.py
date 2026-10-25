import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage
from typer.testing import CliRunner

from story_engine.agents import character, curator, narrator, world as world_agent
from test_extract import fake
from story_engine.cli import app
from story_engine.runs import RunMeta
from story_engine.world.io import append_event, append_scene, load_state, read_events, save_state
from story_engine.world.models import Event, SceneRecord

ROOT = Path(__file__).resolve().parents[2]


def files(path):
    return {p.relative_to(path).as_posix(): p.read_bytes()
            for p in path.rglob('*') if p.is_file()}


@pytest.mark.parametrize('failure', [None, 'error', 'cost', 'summary', 'dry_run'])
@pytest.mark.parametrize('stop_after', [False, True])
def test_world_day(tmp_path, monkeypatch, failure, stop_after):
    for name in ('config', 'prompts', 'cards'):
        shutil.copytree(ROOT / name, tmp_path / name)
    for slug in ('agnea', 'throne'):
        destination = tmp_path / 'kb/characters' / slug
        destination.mkdir(parents=True)
        shutil.copy2(ROOT / 'kb/characters' / slug / f'{slug}.md', destination)
    world = tmp_path / 'worlds/test'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    (world / 'memory/agnea.md').write_bytes(b'Previous memory\r\n')
    # The World fake keeps agnea and throne apart to exercise day orchestration, so no
    # encounter produces a scene; inject two (with a backing event each, for the narrator's
    # grounding check) so the curator (which now picks scenes) has something to choose from.
    append_event(world, Event(id=0, day=1, part='morning', place='cropdale', scene='1', round=1,
                              actor='agnea', type='action', content='Agnea arrives at the festival.',
                              intent='Explore', perceived_by=['agnea']))
    append_event(world, Event(id=0, day=1, part='morning', place='cropdale', scene='2', round=1,
                              actor='agnea', type='action', content='Agnea settles for the evening.',
                              intent='Explore', perceived_by=['agnea']))
    append_scene(world, SceneRecord(id='1', day=1, part='morning', place='cropdale',
                                    participants=['agnea'], first_event_id=1, last_event_id=1,
                                    rounds=1, end='one_left'))
    append_scene(world, SceneRecord(id='2', day=1, part='evening', place='cropdale',
                                    participants=['agnea'], first_event_id=2, last_event_id=2,
                                    rounds=1, end='one_left'))
    before = files(world)
    monkeypatch.chdir(tmp_path)
    clients = []

    class FakeClient:
        def __init__(self, *, options):
            assert failure != 'dry_run', 'dry run opened an SDK session'
            self.is_curator = options.tools == []
            self.is_narrator = options.tools == ['Read']
            self.is_world = options.system_prompt.startswith('# World')
            self.calls = []
            clients.append(self)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def query(self, request):
            self.request = json.loads(request)
            self.calls.append(self.request)

        async def receive_response(self):
            state = load_state(world)
            if self.is_curator:
                reply = json.dumps(dict(
                    acts=[{'scene': '1', 'pov': 'agnea'}, {'scene': '2', 'pov': 'agnea'}], why='A choice.'))
            elif self.is_narrator:
                beats = self.request['beats']
                if beats:
                    rounds, events = [beats[0]['round']], []
                else:
                    rounds, events = [], [e['id'] for e in self.request['part_of_day_events']]
                reply = json.dumps(dict(paragraphs=[
                    {'text': '# Agnea at the Festival', 'rounds': rounds, 'events': events},
                    {'text': 'Agnea looked around.', 'rounds': rounds, 'events': events},
                ]))
            elif self.is_world:
                if failure == 'error' and state.clock.part == 'afternoon':
                    raise RuntimeError('fake error')
                if self.request['call'] == 'adjudicate':
                    # Keep the characters apart so this test exercises the day orchestration.
                    data = dict(call='adjudicate', encounters=[], verdicts=dict(
                        agnea=dict(involves=[], status='settled', outcome='Agnea looks around Cropdale.',
                                  where='cropdale', spot=None),
                        throne=dict(involves=[], status='settled', outcome='Throné stays at the festival grounds.',
                                   where='festival_grounds', spot=None)))
                else:
                    data = dict(call='offscreen', events=[], people={},
                               situations=[s.model_dump(include={"id", "status", "next", "due", "people"}) for s in state.situations],
                               places=[p.model_dump() for p in state.places],
                               situation_notes={s.id: 'Unchanged.' for s in state.situations})
                reply = json.dumps(data)
            elif self.request.get('call') == 'end_of_day':
                if failure == 'summary' and self is clients[1]:
                    raise RuntimeError('summary failed')
                reply = json.dumps(dict(call='end_of_day',
                                        summary='# Today\nVisited the stalls.\n## Changed\nFound a plan.\n## Wants\nRest.'))
            elif self.request.get('call') == 'part_of_day':
                reply = json.dumps(dict(call='plan', intent='Explore', where='cropdale',
                                        spot=None, aim='Look around the stalls.'))
            else:
                reply = json.dumps(dict(call='action', intent='Explore', move='act', urge=2,
                                        action='Looks around.', say=''))
            cost = 11.0 if failure == 'cost' and state.clock.part == 'afternoon' else .01 * len(self.calls)
            yield ResultMessage('success', 1, 1, False, 1, 'fake', result=reply,
                                total_cost_usd=cost, usage={'cache_read_input_tokens': 10})

    monkeypatch.setattr(curator, 'ClaudeSDKClient', FakeClient)
    monkeypatch.setattr(narrator, 'ClaudeSDKClient', FakeClient)
    monkeypatch.setattr(character, 'ClaudeSDKClient', FakeClient)
    monkeypatch.setattr(world_agent, 'ClaudeSDKClient', FakeClient)
    fake(monkeypatch, [dict(call='extract', claims=[]), dict(call='verdicts', verdicts=[])])
    args = ['world', 'run', 'test'] + (['--stop-after', 'day'] if stop_after else [])
    if failure == 'dry_run':
        args += ['--dry-run']
    result = CliRunner().invoke(app, args)
    run = next((tmp_path / 'runs').iterdir())
    meta = RunMeta.model_validate_json((run / 'meta.json').read_bytes())
    trace = [json.loads(line) for line in (run / 'trace.jsonl').read_text().splitlines()]
    assert meta.mode == 'simulation' and meta.world_id == 'test' and meta.day == 1
    if failure in ('error', 'cost', 'summary'):
        assert result.exit_code == 1, result.output
        expected_part = 'night' if failure == 'summary' else 'afternoon'
        assert load_state(world).clock.model_dump() == dict(day=1, part=expected_part)
        completed = {'morning', 'afternoon', 'evening'} if failure == 'summary' else {'morning'}
        assert {e.part for e in read_events(world)} == completed
        assert load_state(world).characters['throne'].where == 'festival_grounds'
        assert files(run / 'world_before') == {k: v for k, v in files(world).items()
                                              if k in ('state.json', 'events.jsonl', 'scenes.jsonl')
                                              or k.startswith('memory/')}
        assert (run / 'world_failed/state.json').exists()
        assert (run / 'world_failed/events.jsonl').exists()
        assert (run / 'world_failed/memory/agnea.md').read_bytes() == b'Previous memory\r\n'
        assert (world / 'memory/agnea.md').read_bytes() == b'Previous memory\r\n'
        assert not (world / 'memory/throne.md').exists()
        assert meta.status == ('stopped' if failure == 'cost' else 'failed')
        assert meta.error and trace[-1]['error'] == meta.error
        if failure in ('error', 'cost'):
            morning = read_events(world)
            failure = None
            clients.clear()
            resumed = CliRunner().invoke(app, args)
            assert resumed.exit_code == 0, resumed.output
            assert all(c.calls[0]['part'] == 'afternoon' for c in clients[:2])
            for client, slug in zip(clients[:2], ('agnea', 'throne')):
                assert client.calls[0]['perceived'] == [
                    e.model_dump(exclude={'intent', 'perceived_by'})
                    for e in morning if slug in e.perceived_by]
                assert (world / 'memory' / f'{slug}.md').read_text().startswith('# Today')
            assert {e['id'] for e in clients[2].calls[0]['events']} >= {e.id for e in morning if not e.op_only}
            assert read_events(world)[:len(morning)] == morning
            assert load_state(world) == type(load_state(world)).model_validate_json((world / "state.json").read_text())
            assert load_state(world).clock.model_dump() == dict(day=2, part='morning')
    elif failure == 'dry_run':
        assert result.exit_code == 0, result.output
        assert files(world) == before and clients == []
        assert meta.status == 'dry_run'
    else:
        assert result.exit_code == 0, result.output
        assert meta.status == ('stopped' if stop_after else 'passed')
        assert {(e.day, e.part) for e in read_events(world)} == {
            (1, p) for p in ('morning', 'afternoon', 'evening', 'night')}
        assert load_state(world) == type(load_state(world)).model_validate_json((world / "state.json").read_text())
        assert load_state(world).clock.model_dump() == dict(day=2, part='morning')
        assert len(clients) == (4 if stop_after else 7)
        assert (run / "episode.json").exists() == (not stop_after)
        for client, slug in zip(clients[:2], ('agnea', 'throne')):
            assert [r['call'] for r in client.calls] == ['part_of_day'] * 4 + ['end_of_day']
            assert client.calls[-1]['perceived']  # includes the final tick's perceptions
            assert (world / 'memory' / f'{slug}.md').read_text().startswith('# Today')
        assert len([r for r in trace if r.get('stage') == 'character_summary']) == 2
        assert all('call_cost_usd' in r for r in trace if r['type'] == 'stage_usage')


def test_day_from_evening(tmp_path, monkeypatch):
    """A resumed world only simulates the remaining parts of its current day."""
    import asyncio
    from story_engine import simulation
    world = tmp_path / 'world'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    state = load_state(world)
    state.clock.part = 'evening'
    save_state(world, state)
    parts = []

    class Agent:
        async def summarize(self, events):
            return 'Memory'

    class Session:
        def __init__(self, *args):
            self.day = 1
            self.characters = {slug: Agent() for slug in state.characters}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    async def tick(world_dir, run_dir, *, session):
        parts.append(state.clock.part)
        if state.clock.part == 'evening':
            state.clock.part = 'night'
        else:
            state.clock.day, state.clock.part = 2, 'morning'
        return state

    monkeypatch.setattr(simulation, 'TickSession', Session)
    monkeypatch.setattr(simulation, 'run_tick', tick)
    asyncio.run(simulation.run_day(world, tmp_path))
    assert parts == ['evening', 'night']
