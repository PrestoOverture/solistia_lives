"""Event sourcing: atomic groups, authoritative log, and a single state writer."""
import json
import shutil
from pathlib import Path

import pytest

from story_engine.world.io import commit_event as _commit_event, create_world, load_state, read_events, save_state
from story_engine.world.models import Event, WorldState
from story_engine.world.ops import OPS, reduce_ops

def commit_event(world, event):
    return _commit_event(world, event, authority=None)


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def world(tmp_path):
    state = WorldState.model_validate_json((ROOT / 'tests/fixtures/worlds/agnea_throne/state.json').read_text())
    return create_world(list(state.characters), 'cropdale', 'Festival', state, worlds_dir=tmp_path)


def event(world, ops, **changes):
    state = load_state(world)
    return Event(id=0, **state.clock.model_dump(), place='cropdale', actor='world',
                 type='state_change', content='', perceived_by=[], ops=OPS.validate_python(ops), **changes)


def test_fold_ignores_corrupt_missing_or_stale_cache(world):
    before = load_state(world)
    commit_event(world, event(world, [dict(op='clock', day=2, part='morning')]))
    after = load_state(world)
    assert after.clock.day == 2
    for data in ('broken json', before.model_dump_json()):
        (world / 'state.json').write_text(data)
        assert load_state(world) == after
    (world / 'state.json').unlink()
    assert load_state(world) == after


def test_atomic_ordered_operations_and_prose_changes_nothing(world):
    before = load_state(world)
    raw = [dict(op='place', slug='new_place', add_details=['A bench']),
           dict(op='move', who='agnea', place='new_place', spot='bench')]
    committed = commit_event(world, event(world, raw))
    assert load_state(world).characters['agnea'].where == 'new_place'
    assert committed.id == 1
    stable = {p.name: p.read_bytes() for p in world.iterdir() if p.is_file()}
    with pytest.raises(ValueError, match='where'):
        commit_event(world, event(world, [dict(op='clock', day=9, part='night'),
                                         dict(op='move', who='agnea', place='missing', spot=None)]))
    assert stable == {p.name: p.read_bytes() for p in world.iterdir() if p.is_file()}
    assert reduce_ops(before, OPS.validate_python(raw), event_id=1) == load_state(world)
    snapshot = load_state(world)
    commit_event(world, event(world, [], **{'resolution': None}))
    assert load_state(world) == snapshot
    assert before.characters['agnea'].where == 'festival_grounds'


def test_all_legacy_state_writes_are_ops(world, monkeypatch):
    from story_engine.world import io
    calls = []
    original = io._atomic_write
    def write(path, content):
        if path.name == 'state.json':
            calls.append(read_events(world)[-1])
        return original(path, content)
    monkeypatch.setattr(io, '_atomic_write', write)
    state = load_state(world)
    state.characters['agnea'].goals = ['A revised goal']
    state.clock.day = 2
    save_state(world, state)
    assert len(calls) == 1 and {op.op for op in calls[0].ops} == {'goals', 'clock'}
    assert load_state(world) == WorldState.model_validate_json((world / 'state.json').read_text())


def test_pre_genesis_world_is_read_only(world):
    (world / 'genesis.json').unlink()
    assert load_state(world)
    before = (world / 'state.json').read_bytes()
    with pytest.raises(ValueError, match='read-only'):
        save_state(world, load_state(world))
    assert (world / 'state.json').read_bytes() == before


def test_ten_op_types_fold_with_stable_commitment_ids(world):
    state = load_state(world)
    situation = state.situations[0].model_dump()
    situation['id'] = 'new-situation'
    ops = [dict(op='place', slug='new-place', add_details=['A gate']),
           dict(op='introduce', name='Host', where='new-place', spot='gate', wants=['Help'], commitments=[]),
           dict(op='move', who='Host', place='cropdale', spot=None),
           dict(op='promise', who='Host', what='Meet', where='cropdale', day=1, part='night'),
           dict(op='wants', person='Host', wants=['Rest']),
           dict(op='goals', main='agnea', goals=['Meet Host']),
           dict(op='open', situation=situation),
           dict(op='situation', id='new-situation', status='resolved'),
           dict(op='clock', day=1, part='night')]
    committed = commit_event(world, event(world, ops, scene='1', round=1))
    state = load_state(world)
    commitment = state.people['Host'].commitments[0]
    assert commitment.id == f'{committed.id}:3' and commitment.scene == '1'
    commit_event(world, event(world, [dict(op='release', who='Host', id=commitment.id, how='kept')], scene='1', round=2))
    assert load_state(world).people['Host'].commitments == []
    assert load_state(world).situations[-1].status == 'resolved'
    assert load_state(world) == WorldState.model_validate_json((world / 'state.json').read_text())


def test_op_only_events_hidden_from_world_curator_and_narrator(world, tmp_path):
    from story_engine.agents.curator import _build_payload
    from story_engine.agents.narrator import act_scene_events, act_transition_events
    from story_engine.agents.world import WorldAgent
    from story_engine.config import load_configs
    from story_engine.trace import TraceWriter
    from story_engine.world.models import SceneRecord
    committed = commit_event(world, event(world, [dict(op='clock', day=1, part='afternoon')]))
    in_scene = commit_event(world, event(world, [dict(op='place', slug='cropdale', add_details=['Gate'])], scene='1', round=1))
    agent = WorldAgent(ROOT, tmp_path, world, load_configs()[0].world, 1, TraceWriter(tmp_path))
    assert agent._new_events(load_state(world), [committed, in_scene]) == []
    scene = SceneRecord(id='1', day=1, part='afternoon', place='cropdale', participants=['agnea'],
                        first_event_id=in_scene.id, last_event_id=in_scene.id, rounds=1, end='quiet')
    assert _build_payload([committed, in_scene], [scene], ['agnea']) == []
    assert act_scene_events([committed, in_scene], '1') == []
    assert act_transition_events([committed, in_scene], [scene], scene) == []


def test_legacy_world_run_rejected_before_opening_sessions(tmp_path, monkeypatch):
    from typer.testing import CliRunner
    from story_engine.cli import app
    world = tmp_path / 'worlds/legacy'
    shutil.copytree(ROOT / 'tests/fixtures/worlds/agnea_throne', world)
    (world / 'genesis.json').unlink()
    before = {p.relative_to(world): p.read_bytes() for p in world.rglob('*') if p.is_file()}
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ['world', 'run', 'legacy', '--dry-run'])
    assert result.exit_code == 1 and 'read-only' in result.output
    assert not (tmp_path / 'runs').exists()
    assert {p.relative_to(world): p.read_bytes() for p in world.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('owner', ['main', 'person'])
def test_genesis_commitment_destinations_must_exist(world, owner):
    data = load_state(world).model_dump()
    commitment = dict(what='Meet', where='unknown-place', day=1, part='night')
    if owner == 'main':
        data['characters']['agnea']['commitments'] = [commitment]
    else:
        data['people']['Host'] = dict(where='cropdale', wants=['Meet'], commitments=[commitment])
    (world / 'genesis.json').write_text(json.dumps(data))
    with pytest.raises(ValueError, match='commitment where must name a slug in places'):
        load_state(world)


def test_introduced_commitment_reference_rejects_whole_group(world):
    before = {p.name: p.read_bytes() for p in world.iterdir() if p.is_file()}
    ops = [dict(op='place', slug='cropdale', add_details=['A gate']),
           dict(op='introduce', name='Host', where='cropdale', wants=['Meet'], commitments=[
               dict(what='Meet', where='unknown-place', day=1, part='night')])]
    with pytest.raises(ValueError, match='commitment where must name a slug in places'):
        commit_event(world, event(world, ops))
    assert {p.name: p.read_bytes() for p in world.iterdir() if p.is_file()} == before


def test_visible_story_rows_keep_ops_and_resolution_metadata():
    from story_engine.agents.curator import _build_payload
    from story_engine.agents.narrator import act_beats, act_scene_events
    from story_engine.world.models import SceneRecord
    act = Event(id=1, day=1, part='morning', place='cropdale', actor='agnea', type='action',
                content='Agnea promises to return.', intent='Meet again', perceived_by=['agnea', 'throne'],
                scene='1', round=1, ops=OPS.validate_python([
                    dict(op='promise', who='agnea', what='Return', where='cropdale', day=1, part='night')]))
    internal = act.model_copy(update={'id': 2, 'type': 'state_change', 'content': ''})
    outcome = Event(id=3, day=1, part='morning', place='cropdale', actor='world', type='world',
                    content='The gate opens.', perceived_by=['agnea', 'throne'], scene='1', round=1,
                    resolves=1, resolution='succeeded', ops=OPS.validate_python([
                        dict(op='place', slug='cropdale', add_details=['An open gate'])]))
    scene = SceneRecord(id='1', day=1, part='morning', place='cropdale', participants=['agnea', 'throne'],
                        first_event_id=1, last_event_id=3, rounds=1, end='quiet')
    events = [act, internal, outcome]
    curated = _build_payload(events, [scene], ['agnea', 'throne'])[0]['events']
    narrated = act_beats(act_scene_events(events, '1'), 'agnea')[0]['events']
    for rows in (curated, narrated):
        assert [row['id'] for row in rows] == [1, 3]
        assert rows[0]['ops'] == [op.model_dump() for op in act.ops]
        assert rows[0]['intent'] == 'Meet again'
        assert rows[1]['ops'] == [op.model_dump() for op in outcome.ops]
        assert (rows[1]['resolves'], rows[1]['resolution']) == (1, 'succeeded')
    other_pov = act_beats(act_scene_events(events, '1'), 'throne')[0]['events']
    assert other_pov[0]['intent'] is None
