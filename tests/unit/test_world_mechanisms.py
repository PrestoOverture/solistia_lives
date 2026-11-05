"""Encounter arrivals and automatic situation expiry, with a fake SDK only."""
import asyncio
import shutil
from pathlib import Path

import pytest

from story_engine.simulation import TickSession, run_tick
from story_engine.world.io import load_state, read_events, read_scenes
from story_engine.world.models import Clock, Person, Situation, WorldState
from test_day_start import fake_sdk

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('with_commitments', [False, True])
@pytest.mark.parametrize('seek', [False, True])
@pytest.mark.parametrize('part,next_day,next_part', [('morning', 1, 'afternoon'), ('night', 2, 'morning')])
def test_arrival_joins_scene_and_clock_event_expires_only_open_past_due(tmp_path, monkeypatch, part, next_day, next_part, seek, with_commitments):
    world, run = tmp_path / 'world', tmp_path / 'run'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    run.mkdir()
    state = load_state(world)
    state.clock.part = part
    state.characters['agnea'].where = 'cropdale'
    state.characters['agnea'].spot = 'village_square'
    state.people['Host'] = Person(where='cropdale', spot='watermill_bridge', wants=['Meet Agnea'], commitments=[])
    due = dict(day=1, part=part)
    state.situations = [Situation(id=id, kind='promise', summary='Meet', touches=['agnea'],
                                 people=['Host'], status=status, next='Meeting ends', due=Clock(**clock))
                        for id, status, clock in [
                            ('arrival', 'open', due), ('also_expired', 'open', due),
                            ('resolved', 'resolved', due), ('dropped', 'dropped', due),
                            ('due_now', 'open', dict(day=next_day, part=next_part)),
                            ('future', 'open', dict(day=next_day + 1, part='morning'))]]
    for member in state.characters.values():
        member.commitments = []
    if with_commitments:
        from story_engine.world.models import Commitment
        for who, member in [('agnea', state.characters['agnea']), ('Host', state.people['Host'])]:
            member.commitments = [Commitment(what='Meet', where='cropdale', **clock, id=id)
                                  for id, clock in [(None, due), ('past', dict(day=0, part='night')),
                                                    ('now', dict(day=next_day, part=next_part)),
                                                    ('future', dict(day=next_day + 1, part='morning'))]]
    for name in ('genesis.json', 'state.json'):
        (world / name).write_text(state.model_dump_json())
    seen_scene = []

    def respond(client, request):
        call = request['call']
        if call == 'part_of_day':
            slug = ('agnea', 'throne')[clients.index(client)]
            character = state.characters[slug]
            return dict(call='plan', kind='attempt' if slug == 'agnea' else 'go',
                        intent='Meet', aim='Wait here.', where=None if slug == 'agnea' else character.where,
                        spot=None if slug == 'agnea' else character.spot)
        if call == 'adjudicate':
            ops = [dict(op='introduce', name='Visitor', sex='f', where='cropdale',
                        spot='village_square', wants=['Meet Agnea'])]
            if not seek:
                return dict(call=call, ops=ops)
            return dict(call=call, ops=[dict(op='move', who='Host', place='cropdale', spot='village_square'), *ops],
                        encounters=[dict(mains=['agnea'], minor=['Host'])])
        if call == 'scene_round':
            seen_scene.append(request)
            assert load_state(world).people['Host'].spot == ('village_square' if seek else 'watermill_bridge')
            return dict(call=call)
        if call == 'scene_move':
            return dict(call='action', move='wait', urge=0, intent='Wait', action='', say='')
        assert call == 'offscreen'
        return dict(call=call, situation_notes={s.id: 'Unchanged.' for s in state.situations if s.status == 'open'})

    clients = fake_sdk(monkeypatch, respond)

    async def exercise():
        async with TickSession(world, run, root=ROOT) as session:
            return await run_tick(world, run, session=session)

    result = asyncio.run(exercise())
    assert seen_scene
    scene, = read_scenes(world)
    assert scene.participants == (['agnea', 'Host', 'Visitor'] if seek else ['agnea', 'Visitor'])
    assert (scene.place, scene.spot) == ('cropdale', 'village_square')
    arrivals = [e for e in read_events(world) if any(getattr(op, 'who', None) == 'Host' for op in e.ops)]
    arrivals = [e for e in arrivals if any(op.op == 'move' for op in e.ops)]
    assert len(arrivals) == int(seek)
    if seek:
        assert arrivals[0].ops[0].op == 'move'
    clock_event = read_events(world)[-1]
    assert [op.model_dump() for op in clock_event.ops] == [
        dict(op='clock', day=next_day, part=next_part),
        *[dict(op='situation', id=id, status='dropped') for id in ('arrival', 'also_expired')],
        *([dict(op='release', who=who, id=id, how='broken')
           for who in ('agnea', 'Host') for id in (f'genesis:{who}:0', 'past')]
          if with_commitments else [])]
    if with_commitments:
        for member in (result.characters['agnea'], result.people['Host']):
            assert [c.id for c in member.commitments] == ['now', 'future']
    assert [s.status for s in result.situations] == ['dropped', 'dropped', 'resolved', 'dropped', 'open', 'open']
    for before, after in zip(state.situations, result.situations):
        assert before.model_dump(exclude={'status'}) == after.model_dump(exclude={'status'})
    assert result == load_state(world) == WorldState.model_validate_json((world / 'state.json').read_text())
