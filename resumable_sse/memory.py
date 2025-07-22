from collections import defaultdict
from typing import AsyncGenerator
import asyncio
from .base import BaseSSEStreamer, ContentStream
from .state import ChatState


class MemorySSEStreamer(BaseSSEStreamer):
    def __init__(self, end_marker: str = "[END]", limit: int = 3):
        super().__init__(end_marker)
        self._store = defaultdict(list)
        self._events = defaultdict(asyncio.Event)
        self._states = defaultdict(str)  # "generating", "[END]", ""
        self._generation_counts = defaultdict(int)  # session_id -> generation count
        self.limit = limit

    async def push(self, session_id: str, data: str) -> None:
        self._store[session_id].append(data)
        self._events[session_id].set()

    async def mark_end(self, session_id: str) -> None:
        await self.push(session_id, self.end_marker)

    async def clear(self, session_id: str) -> None:
        self._store.pop(session_id, None)
        self._states.pop(session_id, None)
        self._events.pop(session_id, None)
        self._generation_counts.pop(session_id, None)

    async def _get_state(self, session_id: str) -> str:
        return self._states.get(session_id, "")

    async def _set_state(self, session_id: str, state: str) -> None:
        self._states[session_id] = state

    async def check_generation_limit(self, state: str, session_id: str) -> bool:
        if state in (ChatState.GENERATING, ChatState.START):
            count = self._generation_counts.get(session_id, 0)
            self._generation_counts[session_id] = count + 1
            return count < self.limit
        return True

    async def stream(
        self,
        session_id: str,
        generator: ContentStream,
        last_id: str = "0",
    ) -> AsyncGenerator[dict, None]:
        if not await self.maybe_start_generator(session_id, generator):
            yield {"event": "error", "data": "Too many requests"}
            return

        index = int(last_id or 0)

        while True:
            messages = self._store[session_id]

            if index < len(messages):
                chunk = messages[index]
                if chunk == self.end_marker:
                    print("end")
                    yield {"event": "end", "data": ""}
                    break
                yield {"event": "message", "id": str(index), "data": chunk}
                index += 1
                continue
            else:
                self._events[session_id].clear()
                try:
                    await asyncio.wait_for(self._events[session_id].wait(), timeout=3)
                except asyncio.TimeoutError:
                    if await self._get_state(session_id) != ChatState.GENERATING:
                        break

        await self._set_state(session_id, "[Done]")

