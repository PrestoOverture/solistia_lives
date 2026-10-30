"""Typed world operations and the pure, ordered, atomic reducer (D15)."""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_serializer, model_validator

from .models import Clock, Commitment, Person, Place, Situation, WorldModel, WorldState


class Move(WorldModel):
    op: Literal['move'] = 'move'
    who: str
    place: str
    spot: str | None


class Introduce(WorldModel):
    op: Literal['introduce'] = 'introduce'
    name: str
    sex: Literal['m', 'f'] | None = None
    where: str
    spot: str | None = None
    wants: list[str] = Field(min_length=1)
    commitments: list[Commitment] = Field(default_factory=list)


class PlaceOp(WorldModel):
    op: Literal['place'] = 'place'
    slug: str
    add_details: list[str]


class Promise(WorldModel):
    op: Literal['promise'] = 'promise'
    who: str
    what: str
    where: str
    day: int
    part: Literal['morning', 'afternoon', 'evening', 'night']


class Release(WorldModel):
    op: Literal['release'] = 'release'
    who: str
    id: str
    how: Literal['kept', 'broken', 'cancelled']


class Wants(WorldModel):
    op: Literal['wants'] = 'wants'
    person: str
    wants: list[str] = Field(min_length=1)


class Goals(WorldModel):
    op: Literal['goals'] = 'goals'
    main: str
    goals: list[str] = Field(min_length=1, max_length=3)


class Open(WorldModel):
    op: Literal['open'] = 'open'
    situation: Situation


class SituationOp(WorldModel):
    op: Literal['situation'] = 'situation'
    id: str
    status: Literal['open', 'resolved', 'dropped'] | None = None
    next: str | None = None
    due: Clock | None = None
    people: list[str] | None = None

    @model_serializer(mode='wrap')
    def serialize(self, handler):
        return {key: value for key, value in handler(self).items() if value is not None}

    @model_validator(mode='after')
    def has_update(self):
        fields = self.model_fields_set - {'op', 'id'}
        if not fields or any(getattr(self, name) is None for name in fields):
            raise ValueError('situation needs at least one non-null update')
        return self


class ClockOp(WorldModel):
    op: Literal['clock'] = 'clock'
    day: int
    part: Literal['morning', 'afternoon', 'evening', 'night']


Op = Annotated[Move | Introduce | PlaceOp | Promise | Release | Wants | Goals | Open | SituationOp | ClockOp,
               Field(discriminator='op')]
OPS = TypeAdapter(list[Op])


def reduce_ops(state: WorldState, ops: list[Op], *, event_id: int, scene: str | None = None, start_index: int = 0) -> WorldState:
    """Never mutate the input; a bad op rejects the entire group."""
    if not ops:
        return state
    state = WorldState.model_validate(state.model_dump())
    for index, op in enumerate(ops, start_index):
        data = state.model_dump()
        members = {**data['characters'], **data['people']}
        if isinstance(op, Move):
            if op.who not in members:
                raise ValueError('move who must name a character or person')
            members[op.who].update(where=op.place, spot=op.spot)
        elif isinstance(op, PlaceOp):
            existing = next((p for p in data['places'] if p['slug'] == op.slug), None)
            if existing is None:
                data['places'].append(Place(slug=op.slug, details=op.add_details).model_dump())
            else:
                existing['details'] += [detail for detail in op.add_details if detail not in existing['details']]
        elif isinstance(op, Introduce):
            if op.name in members:
                raise ValueError('introduce name must be new')
            person = Person(**op.model_dump(exclude={'op', 'name'}))
            for number, commitment in enumerate(person.commitments):
                commitment.id = f'{event_id}:{index}:{number}'
                commitment.scene = scene
            data['people'][op.name] = person.model_dump()
        elif isinstance(op, Promise):
            if op.who not in members:
                raise ValueError('promise who must name a character or person')
            if op.where not in {p.slug for p in state.places}:
                raise ValueError('promise where must name a place')
            members[op.who]['commitments'].append(Commitment(
                **op.model_dump(exclude={'op', 'who'}), id=f'{event_id}:{index}', scene=scene).model_dump())
        elif isinstance(op, Release):
            if op.who not in members:
                raise ValueError('release who must name a character or person')
            commitments = members[op.who]['commitments']
            if op.id not in {c['id'] for c in commitments}:
                raise ValueError('release id must name an existing commitment of who')
            members[op.who]['commitments'] = [c for c in commitments if c['id'] != op.id]
        elif isinstance(op, Wants):
            if op.person not in data['people']:
                raise ValueError('wants person must name a person')
            data['people'][op.person]['wants'] = op.wants
        elif isinstance(op, Goals):
            if op.main not in data['characters']:
                raise ValueError('goals main must name a main character')
            data['characters'][op.main]['goals'] = op.goals
        elif isinstance(op, Open):
            data['situations'].append(op.situation.model_dump())
        elif isinstance(op, SituationOp):
            situation = next((s for s in data['situations'] if s['id'] == op.id), None)
            if situation is None:
                raise ValueError('situation id must name an existing situation')
            situation.update(op.model_dump(exclude={'op', 'id'}, exclude_unset=True))
        elif isinstance(op, ClockOp):
            data['clock'] = op.model_dump(exclude={'op'})
        state = WorldState.model_validate(data)
    return state
