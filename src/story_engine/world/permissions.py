"""Call authority for the §5.2 operation table; only schema and references are checked."""
from dataclasses import dataclass
from typing import Literal

from .models import Event, WorldState
from .ops import ClockOp, Goals, Introduce, Move, Open, PlaceOp, Promise, Release, SituationOp, Wants, reduce_ops


@dataclass(frozen=True)
class Authority:
    call: Literal['code', 'encounter', 'scene_round', 'character_scene', 'person_scene',
                  'day_start', 'character_day_start', 'offscreen']
    actor: str = 'world'


def validate_ops(state: WorldState, event: Event, authority: Authority) -> WorldState:
    """Validate each permission against the same intermediate state as the reducer."""
    call, actor = authority.call, authority.actor
    world = call in {'encounter', 'scene_round', 'person_scene', 'offscreen', 'day_start'}
    for index, op in enumerate(event.ops):
        allowed = False
        if isinstance(op, Move):
            allowed = ((call == 'code' and op.who in state.characters)
                       or (world and call != 'encounter' and op.who in state.people))
        elif isinstance(op, Introduce):
            allowed = call in {'encounter', 'scene_round', 'day_start'}
        elif isinstance(op, PlaceOp):
            allowed = call in {'encounter', 'scene_round', 'offscreen', 'day_start'}
        elif isinstance(op, (Promise, Release)):
            allowed = ((call == 'character_scene' and actor == op.who and actor in state.characters
                        and event.scene is not None)
                       or (world and call != 'encounter' and op.who in state.people))
        elif isinstance(op, Wants):
            allowed = world and call != 'encounter' and op.person in state.people
        elif isinstance(op, Goals):
            allowed = call == 'character_day_start' and actor == op.main and actor in state.characters
        elif isinstance(op, Open):
            allowed = call == 'day_start'
        elif isinstance(op, SituationOp):
            allowed = (call == 'scene_round' and event.scene is not None
                       and event.resolves is not None and event.resolution is not None)
            # The off-screen adapter remains in place until WE3.
        elif isinstance(op, ClockOp):
            allowed = call == 'code'
        if call == 'person_scene':
            subject = getattr(op, 'who', getattr(op, 'person', None))
            allowed = allowed and subject == actor
        if not allowed:
            raise ValueError(f'{call} may not commit {op.op} for this subject')
        # Preserve original op indices when deriving commitment ids.
        state = reduce_ops(state, [op], event_id=event.id, scene=event.scene, start_index=index)
    return state
