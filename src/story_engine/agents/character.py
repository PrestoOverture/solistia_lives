"""One character's persistent session for a single day."""

import json
from pathlib import Path
from typing import Annotated, Literal, Self, Union

from claude_agent_sdk import ClaudeSDKClient, ResultMessage
from pydantic import BaseModel, ConfigDict, Field, model_validator

from story_engine.agents.sdk import (
    run_call, KBHooks, SessionCost, SessionError, ThinkingUsage, json_schema_output, session_error,
    session_options, structured_reply,
)
from story_engine.config import Role
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state, read_events
from story_engine.world.models import Event, PartOfDay


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call: Literal["action"]
    intent: str
    move: Literal["act", "wait", "leave"]
    urge: int
    to: str | None = None
    action: str = Field(max_length=180)
    say: str = Field(max_length=400)

    @model_validator(mode="after")
    def valid_action(self) -> Self:
        if not self.intent.strip():
            raise ValueError("intent must be non-empty")
        if self.move == "act":
            if not 1 <= self.urge <= 3:
                raise ValueError("act urge must be 1-3")
            if not (self.action.strip() or self.say.strip()):
                raise ValueError("act needs a non-empty action or say")
        elif self.urge != 0:
            raise ValueError("wait and leave urge must be 0")
        return self


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call: Literal["plan"]
    intent: str
    where: str
    spot: str | None = None
    aim: str = Field(max_length=140)

    @model_validator(mode="after")
    def valid_plan(self) -> Self:
        if not self.intent.strip():
            raise ValueError("intent must be non-empty")
        if not self.where.strip():
            raise ValueError("where must be non-empty")
        if not self.aim.strip():
            raise ValueError("aim must be non-empty")
        return self


class EndOfDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call: Literal["end_of_day"]
    summary: str

    @model_validator(mode="after")
    def valid_summary(self) -> Self:
        if not self.summary.strip():
            raise ValueError("memory summary must be non-empty")
        return self


class DayStart(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call: Literal["day_start"]
    goals: list[str] = Field(min_length=1, max_length=3)


CharacterReply = Annotated[Union[Action, Plan, EndOfDay, DayStart], Field(discriminator="call")]


class CharacterAgent:
    """Open once per character per day; pass only new perceptions to act."""

    def __init__(
        self, root: Path, run_dir: Path, world_dir: Path, slug: str,
        role: Role, max_turns: int, trace: TraceWriter,
    ) -> None:
        self.root, self.run_dir, self.world_dir = root, run_dir, world_dir
        self.slug, self.role, self.max_turns, self.trace = slug, role, max_turns, trace
        self.client = None
        self.opened = False
        self.turn = 0
        self.cost = SessionCost()
        self.seen: set[int] = set()

    async def __aenter__(self) -> Self:
        if self.opened:
            raise SessionError("CharacterAgent context can only be opened once")
        self.opened = True
        state = load_state(self.world_dir)
        self.prior_events = [event for event in read_events(self.world_dir)
                             if event.day == state.clock.day]
        character = state.characters[self.slug]
        self.opening = {"clock": state.clock.model_dump(), "place": character.where,
                        "goals": character.goals,
                        "commitments": [item.model_dump() for item in character.commitments]}
        memory = self.world_dir / "memory" / f"{self.slug}.md"
        if memory.exists():
            self.opening["memory"] = memory.read_text(encoding="utf-8")
        sources = [self.root / "prompts/character.md", self.root / "cards" / f"{self.slug}.md",
                   self.world_dir / "scene_context.md"]
        prompt = "\n\n".join(path.read_text(encoding="utf-8") for path in sources)
        self.hooks = KBHooks(self.root, self.run_dir, agent=self.slug, turn=1)
        self.options = session_options(self.root, self.run_dir, self.role, prompt,
                                       self.max_turns, self.hooks,
                                       output_format=json_schema_output(CharacterReply))
        self.context = ClaudeSDKClient(options=self.options)
        self.client = await self.context.__aenter__()
        return self

    async def __aexit__(self, *args):
        try:
            return await self.context.__aexit__(*args)
        finally:
            self.client = None

    async def choose(self, part: PartOfDay, perceived: list[Event]) -> Plan:
        return await self._action(perceived, part)

    async def act(self, perceived: list[Event], note: str | None = None) -> Action:
        return await self._action(perceived, note=note)

    async def summarize(self, perceived: list[Event]) -> str:
        """Summarize the day in this character's existing session."""
        return await self._action(perceived, summary=True)

    async def day_start(self) -> list[str]:
        """Revise goals from the opening memory before making any plans."""
        return await self._action([], day_start=True)

    async def _action(self, perceived: list[Event], part: PartOfDay | None = None,
                      note: str | None = None, summary: bool = False,
                      day_start: bool = False) -> Action | Plan | str | list[str]:
        if self.client is None:
            raise SessionError("CharacterAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        events = []
        for event in (self.prior_events if self.turn == 1 else []) + perceived:
            if not event.op_only and self.slug in event.perceived_by and event.id not in self.seen:
                events.append(event.model_dump(exclude={"intent", "perceived_by"}))
                self.seen.add(event.id)
        request = json.dumps({**(self.opening if self.turn == 1 else {}), "perceived": events,
                              **({"note": note} if note else {}),
                              **({"call": "end_of_day", "reply": "JSON {call: 'end_of_day', summary: 'Markdown: what happened, what changed, what you want now'}"} if summary else {}),
                              **({"call": "day_start", "reply": "JSON with call: 'day_start' and 1-3 revised goals"} if day_start else {}),
                              **({"part": part, "call": "part_of_day", "reply": "JSON with call: 'plan'"} if part else {}),
                              # Each request names its reply type in the shared schema.
                              **({"call": "scene_move", "reply": "JSON with call: 'action'"}
                                 if not part and not summary and not day_start else {})},
                             ensure_ascii=False)
        for attempt in range(self.role.retries + 1):
            thinking = ThinkingUsage()
            async def receive_call():
                await self.client.query(request)
                result = None
                structured_output = None
                async for message in self.client.receive_response():
                    self.hooks.observe(message)
                    thinking.observe(message)
                    if isinstance(message, ResultMessage):
                        self.trace.write(
                            "stage_usage", stage=("character_summary" if summary else
                                                  "character_day_start" if day_start else "character_action"), agent=self.slug,
                            turn=self.turn, attempt=attempt + 1, usage=message.usage or {},
                            num_turns=message.num_turns, total_cost_usd=message.total_cost_usd,
                            call_cost_usd=self.cost.delta(message.total_cost_usd),
                            thinking_blocks=thinking.thinking_blocks, thinking_chars=thinking.thinking_chars,
                        )
                        if message.is_error or message.subtype != "success":
                            raise session_error(f"Character session {message.subtype}: "
                                                + ("; ".join(message.errors or []) or message.result or "unspecified SDK error"), self.options.env)
                        result = message.result
                        structured_output = message.structured_output
                return result, structured_output
            result, structured_output = await run_call(receive_call(), role=self.role, trace=self.trace, stage=("character_summary" if summary else "character_day_start" if day_start else "character_action"), agent=self.slug)
            try:
                payload = structured_reply(result, structured_output)
                if day_start:
                    return DayStart.model_validate(payload).goals
                if summary:
                    return EndOfDay.model_validate(payload).summary
                if part:
                    return Plan.model_validate(payload)
                return Action.model_validate(payload)
            except ValueError as error:
                if attempt == self.role.retries:
                    raise SessionError(f"Character action validation failed after {'one retry' if self.role.retries == 1 else str(self.role.retries) + ' retries'}: {error}") from None
                request = f"Reply validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")
