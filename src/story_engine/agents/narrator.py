"""The narrator's per-act writing sessions."""

import itertools
import json
import re
from pathlib import Path

from claude_agent_sdk import ClaudeSDKClient, ResultMessage

from story_engine.agents.sdk import KBHooks, SessionCost, SessionError, session_error, session_options
from story_engine.config import Role, Words
from story_engine.runs import record_api_host
from story_engine.trace import TraceWriter
from story_engine.world.models import Event, SceneRecord

# A grounding marker is one or more marker tags, each either a round marker, e.g.
# "<!-- r:3-5 -->" (rounds of this act's scene), or an event marker, e.g. "<!-- e:12,15 -->"
# (this act's part-of-day events); the whole block must be the last thing in its paragraph (D20).
_ROUND_TAG = r"<!--\s*r:\s*([0-9]+)(?:\s*-\s*([0-9]+))?\s*-->"
_EVENT_TAG = r"<!--\s*e:\s*([0-9]+(?:\s*,\s*[0-9]+)*)\s*-->"
_R_MARKER = re.compile(_ROUND_TAG)
_E_MARKER = re.compile(_EVENT_TAG)
_MARKER_BLOCK = re.compile(r"(?:\s*(?:" + _ROUND_TAG + r"|" + _EVENT_TAG + r"))+\s*\Z")
_QUOTES = ('"', "\u201c", "\u201d")


def act_filename(act_number: int) -> str:
    return f"act_{act_number}.md"


def _paragraphs(text: str) -> list[str]:
    """This act's non-empty paragraphs, blank-line separated; a lone '---' line is not one."""
    return [block for block in re.split(r"\n\s*\n", text.strip()) if block.strip() and block.strip() != "---"]


def strip_markers(text: str) -> str:
    """Remove hidden grounding markers, leaving clean prose for story.md, previous_acts, and
    word counts. The act file on disk keeps the markers for the author's review."""
    cleaned = _R_MARKER.sub("", text)
    cleaned = _E_MARKER.sub("", cleaned)
    cleaned = re.sub(r"[ \t]+$", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned.strip())
    return cleaned + "\n"


def _validate_act(
    text: str, rounds: set[int], allowed_event_ids: set[int],
    speech_rounds: set[int], speech_event_ids: set[int],
) -> tuple[set[int], set[int]]:
    """Check every paragraph's grounding marker; return (cited rounds, cited event ids).
    Raises ValueError naming the offending paragraph (1-based, among non-empty paragraphs) and why."""
    cited_rounds: set[int] = set()
    cited_events: set[int] = set()
    for number, paragraph in enumerate(_paragraphs(text), start=1):
        stripped = paragraph.rstrip()
        match = _MARKER_BLOCK.search(stripped)
        if not match:
            raise ValueError(
                f"paragraph {number} does not end with a <!-- r:N --> or <!-- e:ID --> marker")
        block = stripped[match.start():]
        p_rounds: set[int] = set()
        for r_match in _R_MARKER.finditer(block):
            lo = int(r_match.group(1))
            hi = int(r_match.group(2)) if r_match.group(2) else lo
            if hi < lo:
                raise ValueError(f"paragraph {number} has an invalid round range")
            p_rounds.update(range(lo, hi + 1))
        p_events: set[int] = set()
        for e_match in _E_MARKER.finditer(block):
            p_events.update(int(piece) for piece in e_match.group(1).split(","))
        unknown_rounds = sorted(p_rounds - rounds)
        if unknown_rounds:
            raise ValueError(
                f"paragraph {number} cites round(s) {', '.join(map(str, unknown_rounds))} "
                "outside this act's scene"
            )
        unknown_events = sorted(p_events - allowed_event_ids)
        if unknown_events:
            raise ValueError(
                f"paragraph {number} cites event id(s) {', '.join(map(str, unknown_events))} "
                "outside this act's part-of-day events"
            )
        if any(quote in paragraph for quote in _QUOTES) and not (
            p_rounds & speech_rounds or p_events & speech_event_ids
        ):
            raise ValueError(f"paragraph {number} has dialogue but cites no speech event")
        cited_rounds.update(p_rounds)
        cited_events.update(p_events)
    return cited_rounds, cited_events


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
    options = session_options(root, run_dir, role, prompt, max_turns, hooks, tools=["Read"])
    record_api_host(run_dir, options.env.get("ANTHROPIC_BASE_URL"))
    scene_events = act_scene_events(events, scene.id)
    transition_events = act_transition_events(events, scenes, scene)
    rounds = {event.round for event in scene_events if event.round is not None}
    allowed_event_ids = {event.id for event in transition_events}
    speech_rounds = {event.round for event in scene_events
                     if event.type == "speech" and event.round is not None}
    speech_event_ids = {event.id for event in transition_events if event.type == "speech"}
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
        for attempt in range(2):
            await client.query(request)
            text = None
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
                    if not message.result or not message.result.strip():
                        raise SessionError("Narrator session returned no final text")
                    text = message.result
            if text is None:
                raise SessionError("Narrator session ended without a result")
            try:
                cited_rounds, cited_events = _validate_act(
                    text, rounds, allowed_event_ids, speech_rounds, speech_event_ids)
            except ValueError as error:
                if attempt:
                    raise SessionError(f"Narrator grounding failed after one retry: {error}") from None
                request = (
                    f"Grounding check failed: {error}. Every paragraph must end with a "
                    "<!-- r:N --> or <!-- r:N-M --> marker (rounds of this act's scene), and/or an "
                    "<!-- e:ID,ID --> marker (this act's part-of-day events); a paragraph may cite "
                    "both. Every paragraph with dialogue must cite a round or event containing "
                    "speech. Reply with the full corrected act and nothing else."
                )
                continue
            acts_dir.mkdir(exist_ok=True)
            (acts_dir / act_filename(act_number)).write_text(text, encoding="utf-8")
            trace.write(
                "act_grounding", act=act_number,
                cited_round_share=len(cited_rounds) / len(rounds) if rounds else 0.0,
                cited_rounds=sorted(cited_rounds), cited_events=sorted(cited_events),
            )
            return
    raise AssertionError("unreachable")
