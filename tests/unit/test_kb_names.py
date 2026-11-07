"""People introduced by the World or initializer never share a KB character's name by accident."""

import asyncio
from pathlib import Path

import pytest

from story_engine.kb.entities import CharacterNames
from story_engine.world.io import load_state
from test_day_start import fake_sdk
from test_event_drops import workspace, open_agent, rows

ROOT = Path(__file__).resolve().parents[2]
NAMES = CharacterNames(ROOT / 'kb')


@pytest.mark.parametrize('name,kb,error', [
    ('Thea', None, None),
    ('Order Courier', None, None),
    ('Elena', None, r"KB character's name \(elena_vanstein\)"),
    ('Claude Marston', None, 'claude_blacksnakes'),
    ('mira_the_innkeeper', None, 'mira'),
    ('Elena', 'elena_vanstein', None),
    ('Garud Bristarni', 'garud_bristarni', None),
    ('Elena', 'mira', 'must be the KB character'),
    ('Castti Florenz', 'castti', 'is a main character'),
])
def test_kb_character_names(name, kb, error):
    if error is None:
        NAMES.check(name, kb, {'castti'})
    else:
        with pytest.raises(ValueError, match=error):
            NAMES.check(name, kb, {'castti'})


def test_world_namesake_retries_then_drops(workspace, monkeypatch):
    state = load_state(workspace[0])
    reply = dict(call='adjudicate', ops=[dict(op='introduce', name='Elena', sex='f', where='cropdale',
                                              spot='village_square', wants=['Heal'], commitments=[])])
    clients = fake_sdk(monkeypatch, lambda *_: reply)

    async def exercise():
        async with open_agent(workspace) as agent:
            return await agent.adjudicate(state, {}, [])

    event, _, updated = asyncio.run(exercise())
    assert event is None and 'Elena' not in updated.people
    assert "KB character's name" in clients[0].calls[1]
    assert len(rows(workspace[1], 'event_dropped')) == 1
