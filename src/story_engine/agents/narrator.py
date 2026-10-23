"""The narrator's per-act writing sessions."""

import itertools
import json
import re
from pathlib import Path
from typing import Self

from claude_agent_sdk import ClaudeSDKClient, ResultMessage
from pydantic import BaseModel, ConfigDict, Field, model_validator

from story_engine.agents.sdk import (
    run_call, KBHooks, SessionCost, SessionError, json_schema_output, session_error, session_options,
    structured_reply,
)
from story_engine.config import Role, Words
from story_engine.runs import record_api_host
from story_engine.trace import TraceWriter
from story_engine.world.models import Event, SceneRecord

# A grounding marker is a hidden tag naming what a paragraph tells: a round marker, e.g.
# "<!-- r:3-5 -->" (rounds of this act's scene), or an event marker, e.g. "<!-- e:12,15 -->"
# (this act's part-of-day events). Markers are rendered by code from the narrator's structured
# citations (D20, D27); they are never parsed back out of free text.
_MARKER = re.compile(r"<!--\s*[re]:[^>]*-->")


class NarratorParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    rounds: list[int] = Field(default_factory=list)
    events: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def cites_something(self) -> Self:
        if not self.text.strip():
            raise ValueError("paragraph text must be non-empty")
        if not self.rounds and not self.events:
            raise ValueError("paragraph must cite at least one round or event")
        return self


class NarratorReply(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paragraphs: list[NarratorParagraph] = Field(min_length=1)


def act_filename(act_number: int) -> str:
    return f"act_{act_number}.md"


def strip_markers(text: str) -> str:
    """Remove hidden grounding markers, leaving clean prose for story.md, previous_acts, and
    word counts. The act file on disk keeps the markers for the author's review."""
    cleaned = _MARKER.sub("", text)
    cleaned = re.sub(r"[ \t]+$", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned.strip())
    return cleaned + "\n"


def _format_ranges(values: list[int]) -> str:
    """Compress a sorted list of ints into comma-separated runs, e.g. [1,2,3,5] -> "1-3,5"."""
    ranges: list[list[int]] = []
    for value in sorted(set(values)):
        if ranges and value == ranges[-1][1] + 1:
            ranges[-1][1] = value
        else:
            ranges.append([value, value])
    return ",".join(f"{lo}" if lo == hi else f"{lo}-{hi}" for lo, hi in ranges)


def _markers(paragraph: NarratorParagraph) -> str:
    parts = []
    if paragraph.rounds:
        parts.append(f"<!-- r:{_format_ranges(paragraph.rounds)} -->")
    if paragraph.events:
        parts.append(f"<!-- e:{','.join(str(event) for event in sorted(set(paragraph.events)))} -->")
    return "".join(parts)


def _render_act(paragraphs: list[NarratorParagraph]) -> str:
    """Each paragraph's text, followed by its markers, for review (D20)."""
    blocks = [paragraph.text.rstrip() + _markers(paragraph) for paragraph in paragraphs]
    return "\n\n".join(blocks) + "\n"


def _event_row(event: Event, pov: str) -> dict:
    row = event.model_dump(include={"id", "part", "place", "actor", "type", "content"})
    row["intent"] = event.intent if event.actor == pov else None
    return row


def act_scene_events(events: list[Event], scene_id: str) -> list[Event]:
    """This act's scene events, in order."""
    return [event for event in events if event.scene == scene_id]


def act_beats(scene_events: list[Event], pov: str) -> list[dict]:
    """Group this act's scene events into beats, one beat per round, in round order (D24).
    Scene events are already in round-nondecreasing order, since each round's outcome logs
    the previous round's number before that round's own moves log the current one."""
    return [
        {"round": round_number, "events": [_event_row(event, pov) for event in group]}
        for round_number, group in itertools.groupby(scene_events, key=lambda event: event.round)
    ]


def act_transition_events(events: list[Event], scenes: list[SceneRecord], scene: SceneRecord) -> list[Event]:
    """The part-of-day events since the previous act: this step, since the previous scene of the
    same day (or the start of the day, if this is the day's first scene) up to this scene's start."""
    day_scenes = sorted((other for other in scenes if other.day == scene.day), key=lambda other: other.first_event_id)
    index = next(i for i, other in enumerate(day_scenes) if other.id == scene.id)
    previous = day_scenes[index - 1] if index > 0 else None
    lower = previous.last_event_id if previous is not None else 0
    return [
        event for event in events
        if event.scene is None and event.day == scene.day and lower < event.id < scene.first_event_id
    ]


def _check_citations(paragraphs: list[NarratorParagraph], rounds: set[int], allowed_event_ids: set[int]
                     ) -> tuple[set[int], set[int]]:
    """Check every paragraph's citations reference only this act's scene rounds and part-of-day
    event ids; return (cited rounds, cited event ids). Raises ValueError naming the offending
    paragraph (1-based) and why. Whether a paragraph tells its cited events faithfully is the
    validator's log check (§8), not code (D27)."""
    cited_rounds: set[int] = set()
    cited_events: set[int] = set()
    for number, paragraph in enumerate(paragraphs, start=1):
        unknown_rounds = sorted(set(paragraph.rounds) - rounds)
        if unknown_rounds:
            raise ValueError(
                f"paragraph {number} cites round(s) {', '.join(map(str, unknown_rounds))} "
                "outside this act's scene")
        unknown_events = sorted(set(paragraph.events) - allowed_event_ids)
        if unknown_events:
            raise ValueError(
                f"paragraph {number} cites event id(s) {', '.join(map(str, unknown_events))} "
                "outside this act's part-of-day events")
        cited_rounds.update(paragraph.rounds)
        cited_events.update(paragraph.events)
    return cited_rounds, cited_events


async def narrate_act(
    root: Path, run_dir: Path, events: list[Event], scenes: list[SceneRecord], scene: SceneRecord,
    pov: str, characters: list[str], role: Role, act_words: Words, max_turns: int, trace: TraceWriter,
    act_number: int, previous_acts: list[str],
) -> None:
    """Narrate one act (one scene) into runs/<run_id>/acts/act_<act_number>.md."""
    hooks = KBHooks(root, run_dir, agent="narrator", turn=0)
    sources = [
        root / "prompts/narrator.md",
        root / "prompts/style_spec.md",
        *(root / "cards" / f"{slug}.md" for slug in characters),
    ]
    prompt = "\n\n".join(path.read_text(encoding="utf-8") for path in sources)
    prompt += "\n\n# Scene context\n\n" + (run_dir / "scene_context.md").read_text(encoding="utf-8")
    options = session_options(root, run_dir, role, prompt, max_turns, hooks, tools=["Read"],
                              output_format=json_schema_output(NarratorReply))
    record_api_host(run_dir, options.env.get("ANTHROPIC_BASE_URL"))
    scene_events = act_scene_events(events, scene.id)
    transition_events = act_transition_events(events, scenes, scene)
    rounds = {event.round for event in scene_events if event.round is not None}
    allowed_event_ids = {event.id for event in transition_events}
    request = json.dumps(
        {
            "pov": pov,
            "beats": act_beats(scene_events, pov),
            "part_of_day_events": [_event_row(event, pov) for event in transition_events],
            "previous_acts": previous_acts,
            "words": act_words.model_dump(),
        },
        ensure_ascii=False,
    )
    cost = SessionCost()
    acts_dir = run_dir / "acts"
    async with ClaudeSDKClient(options=options) as client:
        for attempt in range(role.retries + 1):
            async def receive_call():
                await client.query(request)
                result = None
                structured_output = None
                async for message in client.receive_response():
                    hooks.observe(message)
                    if isinstance(message, ResultMessage):
                        trace.write(
                            "stage_usage", stage="narrate_act", agent="narrator", act=act_number,
                            attempt=attempt + 1, usage=message.usage or {}, num_turns=message.num_turns,
                            total_cost_usd=message.total_cost_usd,
                            call_cost_usd=cost.delta(message.total_cost_usd),
                        )
                        if message.is_error or message.subtype != "success":
                            raise session_error(
                                f"Narrator session {message.subtype}: "
                                + ("; ".join(message.errors or []) or message.result or "unspecified SDK error"),
                                options.env,
                            )
                        result = message.result
                        structured_output = message.structured_output
                return result, structured_output
            result, structured_output = await run_call(receive_call(), role=role, trace=trace, stage="narrate_act", agent="narrator")
            try:
                reply = NarratorReply.model_validate(structured_reply(result, structured_output))
                cited_rounds, cited_events = _check_citations(reply.paragraphs, rounds, allowed_event_ids)
            except ValueError as error:
                if attempt == role.retries:
                    raise SessionError(f"Narrator grounding failed after {'one retry' if role.retries == 1 else str(role.retries) + ' retries'}: {error}") from None
                request = f"Grounding check failed: {error}\nReturn the full corrected JSON reply."
                continue
            acts_dir.mkdir(exist_ok=True)
            (acts_dir / act_filename(act_number)).write_text(_render_act(reply.paragraphs), encoding="utf-8")
            trace.write(
                "act_grounding", act=act_number,
                cited_round_share=len(cited_rounds) / len(rounds) if rounds else 0.0,
                cited_rounds=sorted(cited_rounds), cited_events=sorted(cited_events),
            )
            return
    raise AssertionError("unreachable")
