"""Adapt conversation-level fakes to distinct SDK transports that resume a session.

Existing scenario fakes store round counters and history on their session object.
The adapter preserves that state, while returning a fresh transport for each client.
Schema/resume contract tests record the raw clients separately.
"""

from dataclasses import replace


def resumable_fake(session_type):
    sessions = {}

    class Transport:
        def __init__(self, *, options):
            if options.resume:
                self.session = sessions[options.resume]
                self.session_id = options.resume
                self.session.options = options
            else:
                self.session = session_type(options=options)
                self.session_id = f'session-{len(sessions)}'
                sessions[self.session_id] = self.session

        async def __aenter__(self):
            await self.session.__aenter__()
            return self

        async def __aexit__(self, *args):
            return await self.session.__aexit__(*args)

        async def query(self, request):
            await self.session.query(request)

        async def receive_response(self):
            async for message in self.session.receive_response():
                from claude_agent_sdk import ResultMessage
                yield replace(message, session_id=self.session_id) if isinstance(message, ResultMessage) else message

    return Transport
