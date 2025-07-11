from typing import Literal, Optional
from .base import BaseSSEStreamer
from .memory import MemorySSEStreamer
from .redis_stream import RedisSSEStreamer
import redis.asyncio as redis


def get_streamer(
    backend: Literal["memory", "redis"],
    redis_client: Optional[redis.Redis] = None,
    stream_prefix: str = "stream:chat",
    status_prefix: str = "status:chat",
    end_marker: str = "[END]"
) -> BaseSSEStreamer:
    
    if backend == "memory":
        return MemorySSEStreamer(end_marker=end_marker)

    elif backend == "redis":
        if redis_client is None:
            raise ValueError("redis_client is required for Redis backend")
        return RedisSSEStreamer(
            redis_client,
            stream_prefix=stream_prefix,
            status_prefix=status_prefix,
            end_marker=end_marker
        )

    else:
        raise ValueError(f"Unsupported backend: {backend}")
