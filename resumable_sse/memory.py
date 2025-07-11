from collections import defaultdict
from typing import AsyncGenerator
import asyncio
from .base import BaseSSEStreamer, ContentStream


class MemorySSEStreamer(BaseSSEStreamer):
    def __init__(self, end_marker: str = "[END]"):
        super().__init__(end_marker)
        self._store = defaultdict(list)
        self._events = defaultdict(asyncio.Event)
        self._states = defaultdict(str)  # "generating", "[END]", ""

    async def push(self, session_id: str, data: str) -> None:
        self._store[session_id].append(data)
        self._events[session_id].set()

    async def mark_end(self, session_id: str) -> None:
        await self.push(session_id, self.end_marker)

    async def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
        self._states.pop(session_id, None)
        self._events.pop(session_id, None)

    async def _get_state(self, session_id: str) -> str:
        return self._states.get(session_id, "")

    async def _set_state(self, session_id: str, state: str) -> None:
        self._states[session_id] = state

    async def stream(
        self,
        session_id: str,
        generator: ContentStream,
        last_id: str = "0",
    ) -> AsyncGenerator[dict, None]:
        await self.maybe_start_generator(session_id, generator)

        index = int(last_id or 0)

        while True:
            messages = self._store[session_id]
            while index < len(messages):
                chunk = messages[index]
                if chunk == self.end_marker:
                    await self.clear(session_id)
                    yield {"event": "end", "data": ""}
                    return
                yield {"event": "message", "id": str(index), "data": chunk}
                index += 1

            self._events[session_id].clear()
            try:
                await asyncio.wait_for(self._events[session_id].wait(), timeout=3)
            except asyncio.TimeoutError:
                if await self._get_state(session_id) != "generating":
                    break

