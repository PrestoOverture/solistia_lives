from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Role(StrictModel):
    model: str
    effort: Literal["low", "medium", "high", "xhigh", "max"]
    thinking: Literal["off", "adaptive"]


class Models(StrictModel):
    initializer: Role
    character: Role
    world: Role
    rewrite: Role
    baseline: Role
    validator: Role


class Words(StrictModel):
    min: int
    max: int

    @model_validator(mode="after")
    def check_range(self) -> "Words":
        if self.min >= self.max:
            raise ValueError("min must be less than max")
        return self


def valid_stop(value: str) -> str:
    if value == "director":
        return value
    if value.startswith("fixed:") and value[6:].isdigit() and int(value[6:]) >= 1:
        return value
    raise ValueError("must be director or fixed:N with N >= 1")


class Settings(StrictModel):
    words: Words
    parts_of_day: list[Literal["morning", "afternoon", "evening", "night"]]

    @field_validator("parts_of_day")
    @classmethod
    def check_parts(cls, value):
        if value != ["morning", "afternoon", "evening", "night"]:
            raise ValueError("parts_of_day must follow morning, afternoon, evening, night")
        return value
    max_cost_usd: float = Field(gt=0)
    scene_cap: int = Field(gt=0)
    agent_max_turns: int = Field(gt=0)
    validation_rounds: int
    default_stop: str
    scene_context_max_turns: int = Field(gt=0)
    writer_max_turns: int = Field(gt=0)
    suite_parallel: int = Field(gt=0)
    blind_root: Path = Path("~/blind_packets")

    @field_validator("default_stop")
    @classmethod
    def check_stop(cls, value: str) -> str:
        return valid_stop(value)


class ConfigError(Exception):
    pass


def _load(filename: str | Path, schema: type[Models] | type[Settings]) -> Models | Settings:
    try:
        return schema.model_validate(yaml.safe_load(Path(filename).read_text()))
    except ValidationError as error:
        issue = error.errors()[0]
        key = ".".join(str(part) for part in issue["loc"])
        raise ConfigError(f"{filename}: {key}: {issue['msg']}") from None
    except (OSError, yaml.YAMLError) as error:
        raise ConfigError(f"{filename}: {error}") from None


def load_configs(models_file: str | Path = "config/models.yaml") -> tuple[Models, Settings]:
    models = _load(models_file, Models)
    settings = _load("config/settings.yaml", Settings)
    assert isinstance(models, Models) and isinstance(settings, Settings)
    return models, settings
