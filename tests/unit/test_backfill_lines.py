import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from story_engine.cli import app
from story_engine.world.io import load_state, read_events

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def recorded_world(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    world = tmp_path / 'worlds' / 'fixture'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    events = []
    moves = {}
    for day, actor, kind, say in [(1, 'agnea', 'act', 'Hello.'), (1, 'Gus', 'act', 'Welcome.'),
                                   (1, 'throne', 'wait', 'Unspoken.'),
                                   (2, 'agnea', 'leave', 'Goodbye.')]:
        events.append(dict(id=len(events) + 1, day=day, part='morning', place='festival_grounds',
                           actor=actor, type='speech' if kind == 'act' else 'action',
                           content='Opaque content; never split this.', perceived_by=['agnea'],
                           scene='1', round=1, ops=[]))
        moves.setdefault(day, {})[actor] = dict(move=kind, action=f'{actor} waves.', say=say)
    # Include an op so fold preservation exercises a state change as well.
    events.append(dict(id=5, day=2, part='morning', place='festival_grounds', actor='world',
                       type='state_change', content='', perceived_by=[],
                       ops=[dict(op='clock', day=2, part='afternoon')]))
    (world / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    for day, actors in moves.items():
        run = tmp_path / 'runs' / str(day)
        run.mkdir(parents=True)
        (run / 'meta.json').write_text(json.dumps(dict(mode='simulation', world_id='fixture', day=day)))
        (run / 'trace.jsonl').write_text(json.dumps(dict(type='scene_round', scene='1', round=1,
                                                       moves=actors)) + '\n')
    return world, events, moves


def test_backfill_join_idempotent_and_fold_unchanged(recorded_world):
    world, original, moves = recorded_world
    old = read_events(world)
    assert all(event.action is None and event.say is None for event in old)
    state = load_state(world)
    # Identical duplicate traces are fine; unrelated modes/worlds must be ignored.
    source = Path('runs/1')
    shutil.copytree(source, Path('runs/duplicate'))
    for name, mode, world_id in [('other', 'simulation', 'other'), ('eval', 'world_eval', 'fixture')]:
        run = Path('runs') / name
        run.mkdir()
        (run / 'meta.json').write_text(json.dumps(dict(mode=mode, world_id=world_id, day=1)))
        (run / 'trace.jsonl').write_text('invalid unrelated trace')
    result = CliRunner().invoke(app, ['world', 'backfill-lines', 'fixture'])
    assert result.exit_code == 0, result.output
    after = (world / 'events.jsonl').read_bytes()
    rows = [json.loads(line) for line in after.splitlines()]
    for before, row in zip(original, rows):
        assert {k: v for k, v in row.items() if k not in {'move', 'action', 'say'}} == before
        if row['type'] == 'state_change':
            assert row == before
            continue
        move = moves[row['day']][row['actor']]
        assert row['move'] == move['move']
        assert row['action'] == move['action']
        assert row['say'] == (move['say'] if move['move'] != 'wait' else None)
    assert load_state(world) == state
    assert CliRunner().invoke(app, ['world', 'backfill-lines', 'fixture']).exit_code == 0
    assert (world / 'events.jsonl').read_bytes() == after


@pytest.mark.parametrize('failure', ['action', 'say', 'move', 'missing'])
def test_backfill_failure_writes_nothing(recorded_world, failure):
    world, _, _ = recorded_world
    trace = Path('runs/2/trace.jsonl')
    row = json.loads(trace.read_text())
    if failure == 'missing':
        # The first day's rows are valid, so this also tests no partial write.
        trace = Path('runs/1/trace.jsonl')
        row = json.loads(trace.read_text())
        del row['moves']['Gus']
    else:
        row['moves']['agnea'][failure] = 'wait' if failure == 'move' else 'Conflicting value'
        run = Path('runs/conflict')
        run.mkdir()
        shutil.copyfile('runs/2/meta.json', run / 'meta.json')
        trace = run / 'trace.jsonl'
    trace.write_text(json.dumps(row) + '\n')
    original = {p: p.read_bytes() for p in world.rglob('*') if p.is_file()}
    result = CliRunner().invoke(app, ['world', 'backfill-lines', 'fixture'])
    assert result.exit_code == 1
    assert ('No matching move for speech event' if failure == 'missing' else 'Conflicting traces') in result.output
    assert {p: p.read_bytes() for p in world.rglob('*') if p.is_file()} == original
