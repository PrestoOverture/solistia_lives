import asyncio
import json
import shutil
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from story_engine.agents import character, world as world_agent
from story_engine.simulation import TickSession, run_tick
from story_engine.world.io import read_events

ROOT = Path(__file__).resolve().parents[2]


def move(kind='act', urge=2, to=None, action='Waves.', say='Hello.'):
    return dict(intent='Meet the others', move=kind, urge=urge, to=to,
                action=action, say=say)


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
            self.request = json.loads(request)
            requests.append((self.slug, self.request))

        async def receive_response(self):
            if self.is_world:
                data = dict(events=[], state={k: v for k, v in self.request['state'].items() if k != 'clock'})
                if self.request['call'] == 'part_of_day':
                    data['situation_notes'] = {s['id']: 'Unchanged.' for s in data['state']['situations']}
            elif self.request.get('call') == 'part_of_day':
                data = move()
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
    assert all(event.part == 'morning' for event in read_events(world))
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
        assert end['reason'] == 'dispersed' and end['rounds'] == 1
    elif case == 'quiet':
        assert end['reason'] == 'quiet' and end['rounds'] == 2
        assert all(event.content != 'Ignored wait speech' for event in read_events(world))
    else:
        assert end['reason'] == 'scene_cap_reached' and end['rounds'] == len(rounds) == 5
    # Calls within a round see the identical pre-round event snapshot.
    scene_requests = [(slug, req) for slug, req in requests if slug and 'part' not in req]
    for (_, first), (_, second) in zip(scene_requests[::2], scene_requests[1::2]):
        assert first['perceived'] == second['perceived']
    if case == 'tie':
        note = next(req['note'] for slug, req in scene_requests if slug == 'throne' and 'note' in req)
        assert "didn't happen" in note and 'agnea' in note
    resolutions = [req for slug, req in requests if slug is None and req['call'] == 'scene_round']
    for row, resolution in zip(rounds, resolutions):
        assert all(m['move'] != 'act' or slug == row['winner']
                   for slug, m in resolution['choices'].items())
