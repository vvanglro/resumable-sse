from typing import AsyncGenerator
import redis.asyncio as redis
from .base import BaseSSEStreamer, ContentStream
from .state import ChatState


class RedisSSEStreamer(BaseSSEStreamer):
    def __init__(
        self,
        redis_client: redis.Redis,
        stream_prefix: str = "stream:chat",
        status_prefix: str = "status:chat",
        limit_prefix: str = "limit:chat",
        end_marker: str = "[END]",
        limit: int = 3
    ):
        super().__init__(end_marker)
        self.client = redis_client
        self.stream_prefix = stream_prefix
        self.status_prefix = status_prefix
        self.limit_prefix = limit_prefix
        self.limit = limit

    def _stream_key(self, session_id: str) -> str:
        return f"{self.stream_prefix}:{session_id}"

    def _status_key(self, session_id: str) -> str:
        return f"{self.status_prefix}:{session_id}"

    def _limit_prefix(self, session_id: str) -> str:
        return f"{self.limit_prefix}:{session_id}"

    async def push(self, session_id: str, data: str) -> None:
        await self.client.xadd(self._stream_key(session_id), {"data": data})

    async def mark_end(self, session_id: str) -> None:
        await self.push(session_id, self.end_marker)

    async def clear(self, session_id: str) -> None:
        await self.client.delete(self._stream_key(session_id))
        await self.client.delete(self._status_key(session_id))
        await self.client.delete(self._limit_prefix(session_id))

    async def _get_state(self, session_id: str) -> str:
        val = await self.client.hget(self._status_key(session_id), "state")
        return val.decode() if val else ""

    async def _set_state(self, session_id: str, state: str) -> None:
        await self.client.hset(self._status_key(session_id), "state", state)

    async def check_generation_limit(self, state: str, session_id: str) -> bool:
        if state in (ChatState.GENERATING, ChatState.START):
            key = self._limit_prefix(session_id)
            await self.client.set(key, 0, ex=60 * 10, nx=True)
            return await self.client.incr(key) < self.limit
        return True

    async def stream(
            self,
            session_id: str,
            generator: ContentStream,
            last_id: str = "0",
    ) -> AsyncGenerator[dict, None]:
        stream_key = self._stream_key(session_id)
        if not await self.maybe_start_generator(session_id, generator):
            yield {"event": "error", "data": "Too many requests"}
            return

        while True:
            resp = await self.client.xread({stream_key: last_id}, block=3000, count=10)
            if resp:
                _, messages = resp[0]
                for msg_id, msg in messages:
                    last_id = msg_id
                    data = msg[b"data"].decode()
                    if data == self.end_marker:
                        yield {"event": "end", "data": ""}
                        break
                    yield {"event": "message", "id": msg_id.decode(), "data": data}
            else:
                state = await self._get_state(session_id)
                if state != ChatState.GENERATING:
                    break

        await self._set_state(session_id, "[Done]")
