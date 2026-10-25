"""Builders for mocked replies in the new scene/encounter protocol."""


def round_reply(request, *, outcome=None, minor_moves=None, new_people=None, **fields):
    target = request.get('last_winner')
    content = outcome.get('content') if isinstance(outcome, dict) else outcome
    ops = [dict(op='introduce', name=name, **person) for name, person in (new_people or {}).items()]
    return dict(call='scene_round', resolves=target['id'] if target else None,
                resolution='none' if target else None, outcome=content if target else None,
                ops=ops, minor_moves={} if request.get('closing') else (minor_moves or {}), **fields)
