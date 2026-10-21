"""Persistent world artifact schemas (architecture §5)."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

PartOfDay = Literal["morning", "afternoon", "evening", "night"]


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
            raise ValueError("world characters must be unique")
        return self


class Clock(WorldModel):
    day: int
    part: PartOfDay


class Place(WorldModel):
    slug: str
    details: list[str]


class Commitment(WorldModel):
    what: str
    where: str
    day: int
    part: PartOfDay


class CharacterState(WorldModel):
    where: str
    goals: list[str] = Field(min_length=1)
    commitments: list[Commitment]


class Situation(WorldModel):
    id: str
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
    situations: list[Situation]

    @model_validator(mode="after")
    def valid_references(self) -> Self:
        places = {place.slug for place in self.places}
        if any(character.where not in places for character in self.characters.values()):
            raise ValueError("character where must name a slug in places")
        ids = [situation.id for situation in self.situations]
        if len(ids) != len(set(ids)):
            raise ValueError("situation ids must be unique")
        if any(set(situation.touches) - self.characters.keys() for situation in self.situations):
            raise ValueError("situation touches must name only main characters")
        return self


class Event(WorldModel):
    id: int
    day: int
    part: PartOfDay
    place: str
    actor: str
    of: str | None = None
    type: Literal["speech", "action", "world", "state_change"]
    content: str
    intent: str | None = None
    perceived_by: list[str]
    scene: str | None = None


class SceneRecord(WorldModel):
    id: str
    day: int
    part: PartOfDay
    place: str
    participants: list[str]
    first_event_id: int
    last_event_id: int
    rounds: int
    end: str
