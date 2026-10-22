"""The Initializer's scene-start retrieval session."""

import json
import re
from pathlib import Path

from claude_agent_sdk import ClaudeSDKClient, ResultMessage

from story_engine.agents.sdk import (
    KBHooks, SessionCost, SessionError, ThinkingUsage, session_error, session_options,
    structured_reply,
)
from story_engine.config import Role
from story_engine.runs import record_api_host
from story_engine.trace import TraceWriter
from story_engine.world.models import WorldState


async def scene_context(
    root: Path, run_dir: Path, characters: list[str], location: str, scenario: str,
    role: Role, max_turns: int, trace: TraceWriter,
) -> None:
    hooks = KBHooks(root, run_dir, agent="initializer", turn=0)
    prompt = (root / "prompts/initializer_scene_context.md").read_text(encoding="utf-8")
    options = session_options(root, run_dir, role, prompt, max_turns, hooks)
    record_api_host(run_dir, options.env.get("ANTHROPIC_BASE_URL"))
    request = json.dumps({
        "characters": characters, "location": location, "scenario": scenario,
        "kb_path": str((root / "kb").resolve()),
    }, ensure_ascii=False)
    thinking = ThinkingUsage()
    cost = SessionCost()
    async with ClaudeSDKClient(options=options) as client:
        await client.query(request)
        async for message in client.receive_response():
            hooks.observe(message)
            thinking.observe(message)
            if isinstance(message, ResultMessage):
                trace.write(
                    "stage_usage", stage="scene_context", agent="initializer",
                    usage=message.usage or {}, num_turns=message.num_turns,
                    total_cost_usd=message.total_cost_usd,
                    call_cost_usd=cost.delta(message.total_cost_usd),
                    thinking_blocks=thinking.thinking_blocks,
                    thinking_chars=thinking.thinking_chars,
                )
                if message.is_error or message.subtype != "success":
                    raise session_error(
                        f"Initializer session {message.subtype}: "
                        + ("; ".join(message.errors or []) or message.result or "unspecified SDK error"),
                        options.env,
                    )
                if not message.result or not message.result.strip():
                    raise SessionError("Initializer session returned no final text")
                heading = re.search(r"^## ", message.result, re.MULTILINE)
                if heading is None:
                    raise SessionError("Initializer final text has no '## ' heading")
                (run_dir / "scene_context.md").write_text(
                    message.result[heading.start():], encoding="utf-8",
                )
                return
    raise SessionError("Initializer session ended without a result")


async def starting_state(
    root: Path, run_dir: Path, characters: list[str], location: str, situation: str,
    role: Role, max_turns: int, trace: TraceWriter,
) -> WorldState:
    hooks = KBHooks(root, run_dir, agent="initializer", turn=0)
    sources = [root / "prompts/initializer_state.md",
               *(root / "cards" / f"{slug}.md" for slug in characters),
               run_dir / "scene_context.md"]
    prompt = "\n\n".join(path.read_text(encoding="utf-8") for path in sources)
    schema = WorldState.model_json_schema()
    del schema["properties"]["clock"]
    schema["required"].remove("clock")
    options = session_options(root, run_dir, role, prompt, max_turns, hooks,
                              output_format={"type": "json_schema", "schema": schema})
    record_api_host(run_dir, options.env.get("ANTHROPIC_BASE_URL"))
    request = json.dumps({"characters": characters, "location": location,
                          "situation": situation,
                          "kb_path": str((root / "kb").resolve())}, ensure_ascii=False)
    places = {path.stem for path in (root / "kb/locations").rglob("*.md") if path.is_file()}
    cost = SessionCost()
    async with ClaudeSDKClient(options=options) as client:
        for attempt in range(2):
            thinking = ThinkingUsage()
            await client.query(request)
            result = None
            structured_output = None
            async for message in client.receive_response():
                hooks.observe(message)
                thinking.observe(message)
                if isinstance(message, ResultMessage):
                    trace.write(
                        "stage_usage", stage="initializer_state", agent="initializer",
                        attempt=attempt + 1, usage=message.usage or {},
                        num_turns=message.num_turns, total_cost_usd=message.total_cost_usd,
                        call_cost_usd=cost.delta(message.total_cost_usd),
                        thinking_blocks=thinking.thinking_blocks, thinking_chars=thinking.thinking_chars,
                    )
                    if message.is_error or message.subtype != "success":
                        raise session_error(f"Initializer state session {message.subtype}: "
                                            + ("; ".join(message.errors or []) or message.result or "unspecified SDK error"), options.env)
                    result = message.result
                    structured_output = message.structured_output
            try:
                data = _normalize_place_paths(structured_reply(result, structured_output))
                data["clock"] = {"day": 1, "part": "morning"}
                state = WorldState.model_validate(data)
                if set(state.characters) != set(characters):
                    raise ValueError("state characters must match input characters exactly")
                if location not in {place.slug for place in state.places}:
                    raise ValueError("input location must be in places")
                unknown = [place.slug for place in state.places if place.slug not in places]
                if unknown:
                    raise ValueError(
                        f"places {unknown} are not KB location slugs. Use slugs of files under "
                        f"kb/locations/ (such as {location!r}); put a spot inside a place, like a "
                        "house or a stall, in that place's details instead")
                if any(item.due.day < state.clock.day for item in state.situations):
                    raise ValueError("situation due must not precede the starting clock")
                if not 1 <= len(state.situations) <= 3 or any(item.status != "open" for item in state.situations):
                    raise ValueError("starting state must contain 1-3 open situations")
                if len(state.situations) >= 2:
                    if len({item.kind for item in state.situations}) <= 1:
                        raise ValueError("a starting state with two or more situations must have more than one kind")
                    if len({item.due.part for item in state.situations}) <= 1:
                        raise ValueError("a starting state with two or more situations must not have all the same due part")
                return state
            except ValueError as error:
                trace.write(
                    "state_validation_failed", attempt=attempt + 1,
                    error=str(error), raw_reply=result,
                )
                if attempt:
                    raise SessionError(f"Initializer state validation failed after one retry: {error}") from None
                request = f"State validation failed: {error}\nReturn corrected JSON."
    raise SessionError("Initializer state session ended without a state")


def _normalize_place_paths(data: dict) -> dict:
    """Accept path-form slugs ("leaflands/towns/cropdale") as their file stem ("cropdale")."""
    def stem(value):
        return value.rsplit("/", 1)[-1].removesuffix(".md") if isinstance(value, str) else value
    for place in data.get("places") or []:
        if isinstance(place, dict):
            place["slug"] = stem(place.get("slug"))
    for entry in [*(data.get("characters") or {}).values(), *(data.get("people") or {}).values()]:
        if isinstance(entry, dict):
            entry["where"] = stem(entry.get("where"))
            for commitment in entry.get("commitments") or []:
                if isinstance(commitment, dict):
                    commitment["where"] = stem(commitment.get("where"))
    return data
