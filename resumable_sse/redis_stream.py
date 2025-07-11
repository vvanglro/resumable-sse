from typing import AsyncGenerator
import redis.asyncio as redis
from .base import BaseSSEStreamer, ContentStream


class RedisSSEStreamer(BaseSSEStreamer):
    def __init__(
        self,
        redis_client: redis.Redis,
        stream_prefix: str = "stream:chat",
        status_prefix: str = "status:chat",
        end_marker: str = "[END]",
    ):
        super().__init__(end_marker)
        self.client = redis_client
        self.stream_prefix = stream_prefix
        self.status_prefix = status_prefix

    def _stream_key(self, session_id: str) -> str:
        return f"{self.stream_prefix}:{session_id}"

    def _status_key(self, session_id: str) -> str:
        return f"{self.status_prefix}:{session_id}"

    async def push(self, session_id: str, data: str) -> None:
        await self.client.xadd(self._stream_key(session_id), {"data": data})

    async def mark_end(self, session_id: str) -> None:
        await self.push(session_id, self.end_marker)

    async def clear(self, session_id: str) -> None:
        await self.client.delete(self._stream_key(session_id))
        await self.client.delete(self._status_key(session_id))

    async def _get_state(self, session_id: str) -> str:
        val = await self.client.hget(self._status_key(session_id), "state")
        return val.decode() if val else ""

    async def _set_state(self, session_id: str, state: str) -> None:
        await self.client.hset(self._status_key(session_id), "state", state)

    async def stream(
            self,
            session_id: str,
            generator: ContentStream,
            last_id: str = "0",
    ) -> AsyncGenerator[dict, None]:
        stream_key = self._stream_key(session_id)
        await self.maybe_start_generator(session_id, generator)

        while True:
            resp = await self.client.xread({stream_key: last_id}, block=3000, count=10)
            if resp:
                _, messages = resp[0]
                for msg_id, msg in messages:
                    last_id = msg_id
                    data = msg[b"data"].decode()
                    if data == self.end_marker:
                        await self.clear(session_id)
                        yield {"event": "end", "data": ""}
                        return
                    yield {"event": "message", "id": msg_id.decode(), "data": data}
            else:
                state = await self._get_state(session_id)
                if state != "generating":
                    break
