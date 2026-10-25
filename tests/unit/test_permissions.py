"""Accepted and rejected authority for every row of architecture §5.2."""
import pytest

from story_engine.world.models import Clock, Commitment, Event, Person, Place, Situation, WorldState
from story_engine.world.ops import OPS
from story_engine.world.permissions import Authority, validate_ops


@pytest.fixture
def state():
    return WorldState(clock=Clock(day=1, part='evening'), places=[Place(slug='town', details=[])],
                      characters={'agnea': dict(where='town', goals=['Help'], commitments=[
                          dict(id='c1', what='Meet', where='town', day=1, part='night')]),
                                  'throne': dict(where='town', goals=['Rest'], commitments=[])},
                      people={'Host': Person(where='town', wants=['Cook'], commitments=[
                          Commitment(id='p1', what='Cook', where='town', day=1, part='night')])},
                      situations=[Situation(id='s1', kind='occasion', summary='Supper', touches=['agnea'],
                                            people=['Host'], status='open', next='Supper ends',
                                            due=Clock(day=1, part='afternoon'))])


CASES = [
    ('move_main', dict(op='move', who='agnea', place='town', spot='stage'),
     [('code', 'world')], [('scene_round', 'world'), ('character_scene', 'agnea'), ('offscreen', 'world')]),
    ('move_person', dict(op='move', who='Host', place='town', spot='stage'),
     [('scene_round', 'world'), ('offscreen', 'world'), ('person_scene', 'Host')],
     [('code', 'world'), ('encounter', 'world'), ('person_scene', 'Other')]),
    ('introduce', dict(op='introduce', name='Visitor', where='town', wants=['Visit'], commitments=[]),
     [('encounter', 'world'), ('scene_round', 'world'), ('day_start', 'world')],
     [('offscreen', 'world'), ('character_scene', 'agnea'), ('code', 'world')]),
    ('place', dict(op='place', slug='new-town', add_details=['A bridge']),
     [('encounter', 'world'), ('scene_round', 'world'), ('offscreen', 'world'), ('day_start', 'world')],
     [('code', 'world'), ('character_scene', 'agnea'), ('person_scene', 'Host')]),
    ('promise_main', dict(op='promise', who='agnea', what='Meet', where='town', day=1, part='night'),
     [('character_scene', 'agnea')],
     [('character_scene', 'throne'), ('scene_round', 'world'), ('offscreen', 'world'), ('character_day_start', 'agnea')]),
    ('promise_person', dict(op='promise', who='Host', what='Meet', where='town', day=1, part='night'),
     [('scene_round', 'world'), ('offscreen', 'world'), ('person_scene', 'Host')],
     [('character_scene', 'agnea'), ('person_scene', 'Other'), ('encounter', 'world')]),
    ('release_main', dict(op='release', who='agnea', id='c1', how='kept'),
     [('character_scene', 'agnea')], [('character_scene', 'throne'), ('offscreen', 'world'), ('scene_round', 'world')]),
    ('release_person', dict(op='release', who='Host', id='p1', how='kept'),
     [('scene_round', 'world'), ('offscreen', 'world'), ('person_scene', 'Host')],
     [('character_scene', 'agnea'), ('person_scene', 'Other'), ('encounter', 'world')]),
    ('wants', dict(op='wants', person='Host', wants=['Rest']),
     [('scene_round', 'world'), ('offscreen', 'world'), ('day_start', 'world'), ('person_scene', 'Host')],
     [('code', 'world'), ('character_scene', 'agnea'), ('encounter', 'world'), ('person_scene', 'Other')]),
    ('goals', dict(op='goals', main='agnea', goals=['Rest']),
     [('character_day_start', 'agnea')],
     [('character_day_start', 'throne'), ('character_scene', 'agnea'), ('day_start', 'world'), ('offscreen', 'world')]),
    ('open', dict(op='open', situation=dict(id='s2', kind='wish', summary='Visit', touches=['agnea'], people=[],
                                           status='open', next='Visitor departs', due=dict(day=2, part='night'))),
     [('day_start', 'world')], [('scene_round', 'world'), ('offscreen', 'world'), ('encounter', 'world')]),
    ('situation', dict(op='situation', id='s1', status='resolved'),
     [('scene_round', 'world')], [('encounter', 'world'), ('offscreen', 'world'), ('day_start', 'world'),
                                ('character_scene', 'agnea')]),
    ('clock', dict(op='clock', day=2, part='morning'),
     [('code', 'world')], [('scene_round', 'world'), ('offscreen', 'world'), ('day_start', 'world'), ('character_scene', 'agnea')]),
]


@pytest.mark.parametrize('name,raw,call,actor,accepted', [
    (name, raw, call, actor, accepted)
    for name, raw, positive, negative in CASES
    for accepted, entries in [(True, positive), (False, negative)] for call, actor in entries
])
def test_op_table_authority(state, name, raw, call, actor, accepted):
    event = Event(id=8, day=1, part='evening', place='town', actor=actor, type='state_change',
                  content='', perceived_by=[], scene='scene-1', round=1,
                  resolves=7 if call == 'scene_round' else None,
                  resolution='succeeded' if call == 'scene_round' else None, ops=OPS.validate_python([raw]))
    snapshot = state.model_dump()
    if accepted:
        assert validate_ops(state, event, Authority(call, actor, ('morning', 'afternoon', 'evening', 'night'))) != state
    else:
        with pytest.raises(ValueError, match='may not commit'):
            validate_ops(state, event, Authority(call, actor, ('morning', 'afternoon', 'evening', 'night')))
    assert state.model_dump() == snapshot


@pytest.mark.parametrize('resolution', [None, 'none'])
def test_situation_requires_scene_resolution(state, resolution):
    event = Event(id=8, day=1, part='evening', place='town', actor='world', type='world',
                  content='A fact', perceived_by=[], scene='1', round=1,
                  resolves=7 if resolution else None, resolution=resolution,
                  ops=OPS.validate_python([dict(op='situation', id='s1', status='dropped')]))
    if resolution:
        assert validate_ops(state, event, Authority('scene_round')).situations[0].status == 'dropped'
    else:
        with pytest.raises(ValueError, match='may not commit'):
            validate_ops(state, event, Authority('scene_round'))


@pytest.mark.parametrize('clock,fields,accepted', [
    ((1, 'morning'), dict(status='dropped'), False),
    ((1, 'afternoon'), dict(status='dropped'), True),
    ((1, 'evening'), dict(status='dropped'), True),
    ((2, 'morning'), dict(status='dropped'), True),
    ((1, 'evening'), dict(status='resolved'), False),
    ((1, 'evening'), dict(status='open'), False),
    ((1, 'evening'), dict(status='dropped', next='A different ending'), False),
    ((1, 'evening'), dict(status='dropped', due=dict(day=3, part='night')), False),
    ((1, 'evening'), dict(status='dropped', people=[]), False),
    ((1, 'evening'), dict(next='A different ending'), False),
])
def test_offscreen_only_drops_due_situation(state, clock, fields, accepted):
    from story_engine.config import load_settings
    state.clock = Clock(day=clock[0], part=clock[1])
    event = Event(id=8, **state.clock.model_dump(), place='town', actor='world', type='world',
                  content='Any wording', perceived_by=[],
                  ops=OPS.validate_python([dict(op='situation', id='s1', **fields)]))
    authority = Authority('offscreen', parts_of_day=tuple(load_settings().parts_of_day))
    if accepted:
        result = validate_ops(state, event, authority)
        assert result.situations[0].status == 'dropped'
        assert result.situations[0].model_dump(exclude={'status'}) == state.situations[0].model_dump(exclude={'status'})
    else:
        with pytest.raises(ValueError, match='may not commit'):
            validate_ops(state, event, authority)


@pytest.mark.parametrize('how,scene,accepted', [
    ('kept', None, False), ('kept', 'later-scene', True),
    ('broken', None, True), ('cancelled', None, True),
])
def test_scene_promise_kept_only_in_scene(state, how, scene, accepted):
    promised = Event(id=12, **state.clock.model_dump(), place='town', actor='world', type='world',
                     content='An invitation', perceived_by=['agnea'], scene='first-scene', round=1,
                     ops=OPS.validate_python([dict(op='promise', who='Host', what='Meet', where='town', day=1, part='night')]))
    updated = validate_ops(state, promised, Authority('scene_round'))
    promise = updated.people['Host'].commitments[-1]
    assert promise.id == '12:0' and promise.scene == 'first-scene'
    event = Event(id=13, **state.clock.model_dump(), place='town', actor='world', type='world', content='Any text',
                  perceived_by=[], scene=scene, round=2 if scene else None,
                  ops=OPS.validate_python([dict(op='release', who='Host', id=promise.id, how=how)]))
    if accepted:
        result = validate_ops(updated, event, Authority('scene_round' if scene else 'offscreen'))
        assert promise.id not in {c.id for c in result.people['Host'].commitments}
    else:
        with pytest.raises(ValueError, match='kept only in a scene'):
            validate_ops(updated, event, Authority('offscreen'))


def test_promise_provenance_ids_and_atomic_permission_rejection(state):
    ops = OPS.validate_python([
        dict(op='place', slug='town', add_details=['A hall']),
        dict(op='introduce', name='Visitor', where='town', wants=['Meet'], commitments=[
            dict(what='Return', where='town', day=2, part='morning', id='forged', scene='forged')]),
        dict(op='promise', who='Host', what='Return', where='town', day=2, part='morning')])
    event = Event(id=20, **state.clock.model_dump(), place='town', actor='world', type='world', content='Any text',
                  perceived_by=['agnea'], scene='real-scene', round=1, ops=ops)
    result = validate_ops(state, event, Authority('scene_round'))
    visitor = result.people['Visitor'].commitments[0]
    host = result.people['Host'].commitments[-1]
    assert (visitor.id, visitor.scene) == ('20:1:0', 'real-scene')
    assert (host.id, host.scene) == ('20:2', 'real-scene')
    snapshot = state.model_dump()
    event.ops += OPS.validate_python([dict(op='goals', main='agnea', goals=['Forbidden'])])
    with pytest.raises(ValueError, match='may not commit goals'):
        validate_ops(state, event, Authority('scene_round'))
    assert state.model_dump() == snapshot
