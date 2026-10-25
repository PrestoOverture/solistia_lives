"""Persistent world artifact schemas (architecture §5)."""

from typing import TYPE_CHECKING, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from story_engine.kb import normalize_slug

if TYPE_CHECKING:
    from .ops import Op

PartOfDay = Literal["morning", "afternoon", "evening", "night"]
SituationKind = Literal["trouble", "occasion", "promise", "wish", "reunion"]


class WorldModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorldInfo(WorldModel):
    characters: list[str]
    location: str
    situation: str
    created_at: str
    init_run_id: str | None = None

    @model_validator(mode="after")
    def unique_characters(self) -> Self:
        if len(self.characters) != len(set(self.characters)):
            raise ValueError(f"world characters must be unique: {sorted({name for name in self.characters if self.characters.count(name) > 1})}")
        return self


class Clock(WorldModel):
    day: int
    part: PartOfDay


class Place(WorldModel):
    slug: str
    details: list[str]


class Commitment(WorldModel):
    id: str | None = None
    scene: str | None = None
    what: str
    where: str
    day: int
    part: PartOfDay


class CharacterState(WorldModel):
    where: str
    spot: str | None = None
    goals: list[str] = Field(min_length=1)
    commitments: list[Commitment]


class Person(WorldModel):
    where: str
    spot: str | None = None
    wants: list[str] = Field(min_length=1)
    commitments: list[Commitment]


class Situation(WorldModel):
    id: str
    kind: SituationKind = "trouble"
    summary: str
    touches: list[str] = Field(min_length=1)
    people: list[str]
    status: Literal["open", "resolved", "dropped"]
    next: str
    due: Clock


class WorldState(WorldModel):
    clock: Clock
    places: list[Place]
    characters: dict[str, CharacterState]
    people: dict[str, Person] = Field(default_factory=dict)
    situations: list[Situation]

    @model_validator(mode="after")
    def valid_references(self) -> Self:
        places = {place.slug for place in self.places}
        unknown = sorted({character.where for character in self.characters.values() if character.where not in places})
        if unknown:
            raise ValueError(f"character where must name a slug in places: {unknown}")
        main_slugs = set(self.characters)
        for name, person in self.people.items():
            if normalize_slug(name) in main_slugs:
                raise ValueError(f"a person's name must not be a main character's: {name!r}")
        unknown = {name: person.where for name, person in self.people.items() if person.where not in places}
        if unknown:
            raise ValueError(f"person where must name a slug in places: {unknown}")
        ids = [situation.id for situation in self.situations]
        if len(ids) != len(set(ids)):
            raise ValueError(f"situation ids must be unique: {sorted({id for id in ids if ids.count(id) > 1})}")
        unknown = sorted({name for situation in self.situations for name in situation.touches if name not in self.characters})
        if unknown:
            raise ValueError(f"situation touches must name only main characters: {unknown}")
        unknown = sorted({name for situation in self.situations for name in situation.people if name not in self.people})
        if unknown:
            raise ValueError(f"situation people must name entries in people: {unknown}; existing people keys: {sorted(self.people)}")
        return self


class Event(WorldModel):
    id: int
    day: int
    part: PartOfDay
    place: str
    actor: str
    of: str | None = None
    type: Literal["speech", "action", "world", "state_change", "plan"]
    content: str
    intent: str | None = None
    perceived_by: list[str]
    scene: str | None = None
    round: int | None = None
    ops: list['Op'] = Field(default_factory=list)
    resolves: int | None = None
    resolution: Literal['succeeded', 'failed', 'pending', 'none'] | None = None

    @property
    def op_only(self) -> bool:
        return bool(self.ops) and not self.content


class SceneRecord(WorldModel):
    id: str
    day: int
    part: PartOfDay
    place: str
    spot: str | None = None
    participants: list[str]
    first_event_id: int
    last_event_id: int
    rounds: int
    end: str


from .ops import Op
Event.model_rebuild()
