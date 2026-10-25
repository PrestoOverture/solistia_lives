"""D27: length limits are JSON-schema `maxLength` constraints, not code that reads content."""

import pytest
from pydantic import TypeAdapter, ValidationError

from story_engine.agents.character import Action, Plan
from story_engine.agents.world import MinorMove, OffscreenEvent, RoundResolution
from story_engine.world.models import Event

VALID_ACTION = dict(call="action", intent="Find some quiet", move="act", urge=2,
                    action="Throné checks the doorway.", say="")
VALID_PLAN = dict(call="plan", kind="go", intent="Find somewhere quiet", where="cropdale",
                  spot=None, aim="Walk to the tavern.")
VALID_MINOR_MOVE = dict(move="act", urge=1, to=None, action="Waves.", say="Hello!")
VALID_WORLD_EVENT = {"place": "festival_grounds", "actor": "world", "type": "world", "content": "x"}
VALID_EVENT = dict(id=1, day=1, part="morning", place="cropdale", actor="world",
                   of=None, type="world", content="The bell rings.", intent=None,
                   perceived_by=[], scene=None, round=None)


@pytest.mark.parametrize("model,field,max_length", [
    (Action, "action", 180),
    (Action, "say", 400),
    (MinorMove, "action", 180),
    (MinorMove, "say", 400),
    (OffscreenEvent, "content", 280),
    (Plan, "aim", 140),
    (RoundResolution, "outcome", 280),
])
def test_schema_declares_max_length(model, field, max_length):
    schema = TypeAdapter(model).json_schema()
    entry = schema["properties"][field]
    assert entry.get("maxLength", entry.get("anyOf", [{}])[0].get("maxLength")) == max_length


@pytest.mark.parametrize("model,valid,field,max_length", [
    (Action, VALID_ACTION, "action", 180),
    (Action, VALID_ACTION, "say", 400),
    (MinorMove, VALID_MINOR_MOVE, "action", 180),
    (MinorMove, VALID_MINOR_MOVE, "say", 400),
    (OffscreenEvent, VALID_WORLD_EVENT, "content", 280),
    (Plan, VALID_PLAN, "aim", 140),
    (RoundResolution, dict(call="scene_round", resolves=1, resolution="none"), "outcome", 280),
])
def test_over_length_value_fails_validation(model, valid, field, max_length):
    with pytest.raises(ValidationError, match="at most .* characters"):
        model.model_validate({**valid, field: "a" * (max_length + 1)})
    model.model_validate({**valid, field: "a" * max_length})  # at the cap is fine



def test_logged_events_have_no_length_cap():
    """The cap is on the World's reply schema; logged events (incl. a character's action + line) aren't capped."""
    Event.model_validate({**VALID_EVENT, "content": "y" * 600})
