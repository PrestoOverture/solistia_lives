"""One character's persistent session for a single day."""

import json
from pathlib import Path
from typing import Literal, Self

from claude_agent_sdk import ClaudeSDKClient, ResultMessage
from pydantic import BaseModel, ConfigDict, model_validator

from story_engine.agents.sdk import (
    KBHooks, SessionError, ThinkingUsage, json_object, session_error, session_options,
)
from story_engine.config import Role
from story_engine.trace import TraceWriter
from story_engine.world.io import load_state
from story_engine.world.models import Event


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    move: Literal["act", "wait", "leave"]
    urge: int
    to: str | None = None
    action: str
    say: str

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
        self.seen: set[int] = set()

    async def __aenter__(self) -> Self:
        if self.opened:
            raise SessionError("CharacterAgent context can only be opened once")
        self.opened = True
        state = load_state(self.world_dir)
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
                                       self.max_turns, self.hooks)
        self.context = ClaudeSDKClient(options=self.options)
        self.client = await self.context.__aenter__()
        return self

    async def __aexit__(self, *args):
        try:
            return await self.context.__aexit__(*args)
        finally:
            self.client = None

    async def act(self, perceived: list[Event]) -> Action:
        if self.client is None:
            raise SessionError("CharacterAgent must be opened as an async context manager")
        self.turn += 1
        self.hooks.turn = self.turn
        events = []
        for event in perceived:
            if self.slug in event.perceived_by and event.id not in self.seen:
                events.append(event.model_dump(exclude={"intent", "perceived_by"}))
                self.seen.add(event.id)
        request = json.dumps({**(self.opening if self.turn == 1 else {}), "perceived": events},
                             ensure_ascii=False)
        for attempt in range(2):
            thinking = ThinkingUsage()
            await self.client.query(request)
            result = None
            async for message in self.client.receive_response():
                self.hooks.observe(message)
                thinking.observe(message)
                if isinstance(message, ResultMessage):
                    self.trace.write(
                        "stage_usage", stage="character_action", agent=self.slug,
                        turn=self.turn, attempt=attempt + 1, usage=message.usage or {},
                        num_turns=message.num_turns, total_cost_usd=message.total_cost_usd,
                        thinking_blocks=thinking.thinking_blocks, thinking_chars=thinking.thinking_chars,
                    )
                    if message.is_error or message.subtype != "success":
                        raise session_error(f"Character session {message.subtype}: "
                                            + ("; ".join(message.errors or []) or message.result or "unspecified SDK error"), self.options.env)
                    result = message.result
            try:
                if result is None:
                    raise ValueError("character session returned no final text")
                return Action.model_validate(json_object(result))
            except ValueError as error:
                if attempt:
                    raise SessionError(f"Character action validation failed after one retry: {error}") from None
                request = f"Action validation failed: {error}\nReturn corrected JSON."
        raise AssertionError("unreachable")
