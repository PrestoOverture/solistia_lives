"""Shared SDK session configuration and KB access hooks."""

import asyncio
import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from claude_agent_sdk import (
    AssistantMessage, ClaudeAgentOptions, HookMatcher, TextBlock, ThinkingBlock,
    ToolUseBlock, UserMessage,
)
from pydantic import BaseModel

from story_engine.config import Role

KB_TOOLS = ["Read", "Grep", "Glob"]


@dataclass
class ThinkingUsage:
    """Count received thinking blocks without retaining their text or signatures."""

    thinking_blocks: int = 0
    thinking_chars: int = 0

    def observe(self, message: object) -> None:
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ThinkingBlock):
                    self.thinking_blocks += 1
                    self.thinking_chars += len(block.thinking)


@dataclass
class SessionCost:
    """Convert the SDK's session cumulative cost into per-call spend."""

    total: float = 0.0

    def delta(self, total: float | None) -> float:
        if total is None:
            return 0.0
        cost = total - self.total
        self.total = total
        return cost


class SessionError(RuntimeError):
    """A session failure whose diagnostic has been scrubbed of credentials."""


async def run_call(call, *, role: Role, trace, stage: str, agent: str):
    """Bound one query and response, retaining unbounded behavior by default."""
    if role.timeout_s is None:
        return await call
    try:
        return await asyncio.wait_for(call, timeout=role.timeout_s)
    except TimeoutError:
        trace.write("call_timeout", stage=stage, agent=agent, timeout_s=role.timeout_s)
        raise SessionError(f"{stage} ({agent}) timed out after {role.timeout_s}s") from None


def json_object(reply: str) -> dict:
    """Extract a JSON object, tolerating fences or surrounding prose."""
    try:
        data = json.loads(reply)
    except json.JSONDecodeError:
        start, end = reply.find("{"), reply.rfind("}")
        if start < 0 or end < start:
            raise ValueError("reply must be a JSON object") from None
        data = json.loads(reply[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("reply must be a JSON object")
    return data


def structured_reply(result: str | None, structured_output: object) -> dict:
    """Prefer the SDK's parsed structured output; fall back to parsing `result`."""
    if isinstance(structured_output, dict):
        if set(structured_output) == {"reply"} and isinstance(structured_output["reply"], dict):
            return structured_output["reply"]  # a union wrapped by json_schema_output
        return structured_output
    if result is None:
        raise ValueError("session returned no final text")
    return json_object(result)


def session_error(error: object, env: dict[str, str]) -> SessionError:
    message = str(error)
    sensitive = [value for key, value in {**os.environ, **env}.items()
                 if key.startswith("ANTHROPIC_") and value]
    for value in sorted(sensitive, key=len, reverse=True):
        message = message.replace(value, "[redacted]")
    return SessionError(" ".join(message.split()))


def session_environment(root: Path, keys: set[str] | None = None) -> dict[str, str]:
    """Read relay credentials, preferring .env without mutating os.environ."""
    if keys is None:
        keys = {"ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"}
    env = {key: os.environ[key] for key in keys if key in os.environ}
    path = root / ".env"
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or key not in keys:
            continue
        try:
            parts = shlex.split(value, comments=True)
        except ValueError:
            raise ValueError("Invalid quoting in .env credential assignment") from None
        if len(parts) > 1:
            raise ValueError("Invalid .env credential assignment")
        env[key] = parts[0] if parts else ""
    return env


class Retrieval(BaseModel):
    turn: int
    agent: str
    tool: Literal["Read", "Grep", "Glob"]
    file: str
    reason: str | None


class KBHooks:
    def __init__(self, root: Path, run_dir: Path, agent: str, turn: int) -> None:
        self.root = root.resolve()
        self.kb = (self.root / "kb").resolve()
        self.log = run_dir / "retrieval.jsonl"
        self.log.touch(exist_ok=True)
        self.agent = agent
        self.turn = turn
        self.reasons: dict[str, str | None] = {}
        self._message_id: str | None = None
        self._reason: str | None = None

    def observe(self, message: object) -> None:
        """Associate pre-tool prose with tool IDs, including split assistant blocks."""
        if isinstance(message, UserMessage):
            self._reason = None
        if not isinstance(message, AssistantMessage):
            return
        if message.message_id != self._message_id:
            self._reason = None
            self._message_id = message.message_id
        for block in message.content:
            if isinstance(block, TextBlock):
                self._reason = block.text.strip() or None
            elif isinstance(block, ToolUseBlock):
                self.reasons[block.id] = self._reason

    def checked_path(self, tool: str, inputs: dict) -> tuple[str, Path]:
        if tool not in KB_TOOLS:
            raise ValueError("Only Read, Grep, and Glob are permitted")
        key = "file_path" if tool == "Read" else "path"
        raw = inputs.get(key)
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("An explicit path inside kb/ is required")
        path = (self.root / raw).resolve()
        if not path.is_relative_to(self.kb):
            raise ValueError("The path must stay inside kb/")
        if tool in ("Grep", "Glob"):
            # Glob's pattern can otherwise escape an allowed search directory.
            pattern = inputs.get("pattern" if tool == "Glob" else "glob", "")
            if not isinstance(pattern, str) or pattern.startswith(("/", "~")) or ".." in pattern:
                raise ValueError("Search patterns must stay inside the searched path")
            # Grep follows symlinks. Reject searches containing an escaping link.
            if path.is_dir():
                for child in path.rglob("*"):
                    if child.is_symlink() and not child.resolve().is_relative_to(self.kb):
                        raise ValueError("Search contains a symlink outside kb/")
        return key, path

    async def pre_tool_use(self, data: dict, tool_use_id: str | None, context: dict) -> dict:
        if data["tool_name"] == "StructuredOutput":
            # The SDK delivers output_format replies through this built-in tool.
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
        try:
            key, path = self.checked_path(data["tool_name"], data["tool_input"])
        except (ValueError, OSError, RuntimeError):
            # Do not echo paths or arbitrary tool inputs (which can contain secrets).
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": "Only Read/Grep/Glob on paths confined to kb/ are allowed.",
            }}
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "allow",
            "updatedInput": {**data["tool_input"], key: str(path)},
        }}

    async def post_tool_use(self, data: dict, tool_use_id: str | None, context: dict) -> dict:
        if data["tool_name"] == "StructuredOutput":
            return {}
        _, path = self.checked_path(data["tool_name"], data["tool_input"])
        entry = Retrieval(
            turn=self.turn, agent=self.agent, tool=data["tool_name"],
            file=path.relative_to(self.kb).as_posix(),
            reason=self.reasons.pop(tool_use_id or data.get("tool_use_id", ""), None),
        )
        with self.log.open("a", encoding="utf-8") as log:
            log.write(entry.model_dump_json() + "\n")
        return {}


def session_options(
    root: Path, run_dir: Path, role: Role, system_prompt: str, max_turns: int, hooks: KBHooks, *,
    tools: list[str] | None = None, output_format: dict | None = None,
) -> ClaudeAgentOptions:
    env = session_environment(root)
    if role.base_url:
        credentials = session_environment(root, {role.auth_token_env} if role.auth_token_env else set())
        env["ANTHROPIC_BASE_URL"] = role.base_url
        env["ANTHROPIC_AUTH_TOKEN"] = credentials.get(role.auth_token_env, "")
        env.pop("ANTHROPIC_API_KEY", None)
        if role.thinking == "off":
            # The CLI otherwise omits thinking, letting the provider enable it by default.
            env["CLAUDE_CODE_EXTRA_BODY"] = '{"thinking":{"type":"disabled"}}'
        for key in (
            "ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "ANTHROPIC_DEFAULT_OPUS_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL",
        ):
            env[key] = role.model
    optional = {}
    if role.effort is not None:
        optional["effort"] = role.effort
    if role.thinking is not None:
        optional["thinking"] = {"type": "disabled" if role.thinking == "off" else "adaptive"}
    # Keep SDK bookkeeping inside this run, without persisting conversations.
    env["CLAUDE_CONFIG_DIR"] = str((run_dir / ".sdk").resolve())
    return ClaudeAgentOptions(
        cwd=root, system_prompt=system_prompt, model=role.model, **optional,
        max_turns=role.max_turns if role.max_turns is not None else max_turns, tools=KB_TOOLS.copy() if tools is None else tools,
        allowed_tools=KB_TOOLS.copy() if tools is None else tools,
        setting_sources=[], strict_mcp_config=True, env=env,
        verbatim_prompts=True, extra_args={"no-session-persistence": None},
        output_format=output_format,
        # SDK diagnostics may contain relay credentials; never forward them to logs.
        stderr=lambda line: None,
        hooks={
            "PreToolUse": [HookMatcher(hooks=[hooks.pre_tool_use])],
            "PostToolUse": [HookMatcher(hooks=[hooks.post_tool_use])],
        },
    )


def json_schema_output(model: type) -> dict:
    """Build an `output_format` dict from a Pydantic model or TypeAdapter-compatible type."""
    from pydantic import TypeAdapter

    schema = _strip_discriminator(TypeAdapter(model).json_schema())
    variants = schema.pop("oneOf", None) or schema.pop("anyOf", None)
    if variants is not None:
        # The CLI accepts a union only nested under an object root.
        schema = {"type": "object", "$defs": schema.get("$defs", {}),
                  "properties": {"reply": {"anyOf": variants}},
                  "required": ["reply"], "additionalProperties": False}
    return {"type": "json_schema", "schema": schema}


def _strip_discriminator(node):
    """The CLI's strict JSON Schema check rejects OpenAPI's `discriminator`; each
    variant's `call` const already tells the variants apart."""
    if isinstance(node, dict):
        return {key: _strip_discriminator(value) for key, value in node.items() if key != "discriminator"}
    if isinstance(node, list):
        return [_strip_discriminator(value) for value in node]
    return node


def require_person_sex(output_format: dict) -> dict:
    """Require sex only at model creation boundaries; historical artifacts stay optional."""
    for name in ("Person", "Introduce"):
        definition = output_format["schema"].get("$defs", {}).get(name)
        if definition is not None:
            definition["properties"]["sex"] = {
                "type": "string", "enum": ["m", "f"],
                "description": "The person's sex, male (m) or female (f), for appearance and voice.",
            }
            definition.setdefault("required", []).append("sex")
    return output_format
