"""WE1 bridge: translate legacy state replies into the ten operations."""

from .models import WorldState
from .ops import ClockOp, Goals, Introduce, Move, Open, PlaceOp, Promise, Release, SituationOp, Wants


def state_ops(before: WorldState, after: WorldState) -> list:
    ops = []
    places = {p.slug: p for p in before.places}
    for place in after.places:
        added = [detail for detail in place.details
                 if place.slug not in places or detail not in places[place.slug].details]
        if added or place.slug not in places:
            ops.append(PlaceOp(slug=place.slug, add_details=added))
    for name, person in after.people.items():
        if name not in before.people:
            ops.append(Introduce(name=name, **person.model_dump()))
    previous = {**before.characters, **before.people}
    for name, member in {**after.characters, **after.people}.items():
        if name not in previous:
            continue
        old = previous[name]
        if (member.where, member.spot) != (old.where, old.spot):
            ops.append(Move(who=name, place=member.where, spot=member.spot))
        if name in after.characters and member.goals != old.goals:
            ops.append(Goals(main=name, goals=member.goals))
        if name in after.people and member.wants != old.wants:
            ops.append(Wants(person=name, wants=member.wants))
        def terms(commitment):
            return commitment.model_dump(exclude={'id', 'scene'})
        for commitment in old.commitments:
            if not any(terms(c) == terms(commitment) for c in member.commitments):
                ops.append(Release(who=name, id=commitment.id, how='cancelled'))
        for commitment in member.commitments:
            if not any(terms(c) == terms(commitment) for c in old.commitments):
                ops.append(Promise(who=name, **terms(commitment)))
    situations = {s.id: s for s in before.situations}
    for situation in after.situations:
        if situation.id not in situations:
            ops.append(Open(situation=situation))
        else:
            old = situations[situation.id]
            changes = {key: value for key, value in situation.model_dump().items()
                       if key in {'status', 'next', 'due', 'people'} and value != old.model_dump()[key]}
            if changes:
                ops.append(SituationOp(id=situation.id, **changes))
    if before.clock != after.clock:
        ops.append(ClockOp(**after.clock.model_dump()))
    return ops
