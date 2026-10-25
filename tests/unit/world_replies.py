"""Builders for mocked replies in the new scene/encounter protocol."""


def round_reply(request, *, outcome=None, minor_moves=None, new_people=None, **fields):
    target = request.get('last_winner')
    content = outcome.get('content') if isinstance(outcome, dict) else outcome
    ops = [dict(op='introduce', name=name, **person) for name, person in (new_people or {}).items()]
    return dict(call='scene_round', resolution='none' if target else None, outcome=content if target else None,
                ops=ops, minor_moves={} if request.get('closing') else (minor_moves or {}), **fields)


def day_start_reply(*, situations, people=None, places=None):
    ops = [dict(op='place', slug=p['slug'], add_details=p['details']) for p in (places or [])]
    ops += [dict(op='introduce', name=name, **person) for name, person in (people or {}).items()]
    ops += [dict(op='open', situation=s) for s in situations]
    return dict(call='day_start', ops=ops)


def goals_reply(slug, goals):
    return dict(call='day_start', ops=[dict(op='goals', main=slug, goals=goals)])


def commit_fixture_changes(world, state):
    """Set up fixture clocks, goals, people, and places through authorized events."""
    from story_engine.world.adapter import state_ops
    from story_engine.world.io import commit_event, load_state, validate_state
    from story_engine.world.models import Event
    from story_engine.world.permissions import Authority

    before = load_state(world)
    state = validate_state(world, state)
    for op in state_ops(before, state):
        if op.op in {'clock', 'move'}:
            authority = Authority('code')
        elif op.op == 'goals':
            authority = Authority('character_day_start', op.main)
        elif op.op in {'place', 'introduce'}:
            authority = Authority('encounter')
        else:
            raise AssertionError(f'Fixture change needs an explicit event: {op.op}')
        commit_event(world, Event(
            id=0, **before.clock.model_dump(), place=before.places[0].slug, actor='world',
            type='state_change', content='', perceived_by=[], ops=[op]), authority=authority)
