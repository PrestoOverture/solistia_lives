"""Unit tests must never start a real SDK session."""

import sys

import claude_agent_sdk
import pytest

_REAL_CLIENT = claude_agent_sdk.ClaudeSDKClient


@pytest.fixture(autouse=True)
def forbid_live_sdk(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Unit tests must install a fake ClaudeSDKClient')

    for name, module in list(sys.modules.items()):
        if name == 'claude_agent_sdk' or name.startswith('story_engine.'):
            if getattr(module, 'ClaudeSDKClient', None) is _REAL_CLIENT:
                monkeypatch.setattr(module, 'ClaudeSDKClient', forbidden)
