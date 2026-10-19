"""The Director's scene-start retrieval session."""

import json
import re
from pathlib import Path

from claude_agent_sdk import ClaudeSDKClient, ResultMessage

from story_engine.agents.sdk import KBHooks, SessionError, ThinkingUsage, session_error, session_options
from story_engine.config import Role
from story_engine.runs import record_api_host
from story_engine.trace import TraceWriter


async def scene_context(
    root: Path, run_dir: Path, characters: list[str], location: str, scenario: str,
    role: Role, max_turns: int, trace: TraceWriter,
) -> None:
    hooks = KBHooks(root, run_dir, agent="director", turn=0)
    prompt = (root / "prompts/director_scene_context.md").read_text(encoding="utf-8")
    options = session_options(root, run_dir, role, prompt, max_turns, hooks)
    record_api_host(run_dir, options.env.get("ANTHROPIC_BASE_URL"))
    request = json.dumps({
        "characters": characters, "location": location, "scenario": scenario,
        "kb_path": str((root / "kb").resolve()),
    }, ensure_ascii=False)
    thinking = ThinkingUsage()
    async with ClaudeSDKClient(options=options) as client:
        await client.query(request)
        async for message in client.receive_response():
            hooks.observe(message)
            thinking.observe(message)
            if isinstance(message, ResultMessage):
                trace.write(
                    "stage_usage", stage="scene_context", agent="director",
                    usage=message.usage or {}, num_turns=message.num_turns,
                    total_cost_usd=message.total_cost_usd,
                    thinking_blocks=thinking.thinking_blocks,
                    thinking_chars=thinking.thinking_chars,
                )
                if message.is_error or message.subtype != "success":
                    raise session_error(
                        f"Director session {message.subtype}: "
                        + ("; ".join(message.errors or []) or message.result or "unspecified SDK error"),
                        options.env,
                    )
                if not message.result or not message.result.strip():
                    raise SessionError("Director session returned no final text")
                heading = re.search(r"^## ", message.result, re.MULTILINE)
                if heading is None:
                    raise SessionError("Director final text has no '## ' heading")
                (run_dir / "scene_context.md").write_text(
                    message.result[heading.start():], encoding="utf-8",
                )
                return
    raise SessionError("Director session ended without a result")
