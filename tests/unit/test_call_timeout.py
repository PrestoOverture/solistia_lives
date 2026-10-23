"""Per-call deadlines with SDK fakes; no provider calls."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from story_engine.agents import baseline, validation
from story_engine.agents.sdk import KBHooks, SessionCost, SessionError
from story_engine.config import Role, Words, load_configs
from story_engine.eval import world
from story_engine.trace import TraceWriter

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('path,stage,agent', [
    ('baseline', 'baseline_writer', 'baseline'),
    ('judge', 'world_eval', 'world_judge'),
    ('extract', 'extract', 'validator'),
    ('verdicts', 'verdicts', 'validator'),
])
@pytest.mark.parametrize('timeout', [0.05, None])
def test_stalled_response(tmp_path, monkeypatch, path, stage, agent, timeout):
    cancelled = []
    closed = []

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.append(True)

        async def query(self, request):
            pass

        async def receive_response(self):
            try:
                await asyncio.Event().wait()
                yield  # an async iterator that never yields
            finally:
                cancelled.append(True)

    for module in (baseline, world):
        monkeypatch.setattr(module, 'ClaudeSDKClient', Client)
        monkeypatch.setattr(module, 'record_api_host', lambda *args: None)
    (tmp_path / 'scene_context.md').write_text('## Context\n')
    role = Role(model='fake', effort=None, thinking=None, timeout_s=timeout)
    trace = TraceWriter(tmp_path)

    async def exercise():
        if path == 'baseline':
            call = baseline.baseline_writer(ROOT, tmp_path, [], 'cropdale', 'test',
                                            role, Words(min=1, max=10), 2, trace)
        elif path == 'judge':
            call = world.judge(ROOT, tmp_path,
                               dict(events=[], previous_events=[], outcomes=[]),
                               role, 2, trace, SessionCost())
        else:
            call = validation._call(Client(), '{}', parse=lambda x: x, check=lambda x: None,
                                    hooks=KBHooks(ROOT, tmp_path, 'validator', 1),
                                    trace=trace, cost=SessionCost(), options=SimpleNamespace(env={}),
                                    stage=stage, role=role)
        task = asyncio.create_task(call)
        if timeout is None:
            await asyncio.sleep(0.08)
            assert not task.done(), 'null timeout must keep waiting'
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(SessionError, match='timed out after 0.05s'):
                await asyncio.wait_for(task, timeout=1)

    asyncio.run(exercise())
    assert cancelled == [True]
    if path in ('baseline', 'judge'):
        assert closed == [True]
    rows = [json.loads(line) for line in trace.path.read_text().splitlines()] if trace.path.exists() else []
    if timeout is None:
        assert rows == []
    else:
        assert len(rows) == 1
        assert {k: v for k, v in rows[0].items() if k != 'ts'} == dict(
            type='call_timeout', stage=stage, agent=agent, timeout_s=0.05)


def test_timeout_config_defaults_and_spark():
    models, _ = load_configs()
    assert all(role.timeout_s is None for role in models.__dict__.values())
    spark, _ = load_configs(ROOT / 'config/models_spark.yaml')
    assert all(role.timeout_s == 600 for role in spark.__dict__.values())
