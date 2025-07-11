import asyncio
from typing import AsyncIterable, Iterator, Any, AsyncGenerator, AsyncIterator, TypeVar, Iterable
from abc import ABC, abstractmethod

T = TypeVar("T")
Content = str | bytes | dict | Any
SyncContentStream = Iterator[Content]
AsyncContentStream = AsyncIterable[Content]
ContentStream = AsyncContentStream | SyncContentStream

class _StopIterationSentinel(Exception):
    pass

def _next(iterator: Iterator[T]) -> T:
    try:
        return next(iterator)
    except StopIteration:
        raise _StopIterationSentinel

async def iterate_in_threadpool(iterator: Iterable[T]) -> AsyncIterator[T]:
    as_iterator = iter(iterator)
    while True:
        try:
            yield await asyncio.to_thread(_next, as_iterator)
        except _StopIterationSentinel:
            break


class BaseSSEStreamer(ABC):
    def __init__(self, end_marker: str = "[END]"):
        self.end_marker = end_marker

    @abstractmethod
    async def push(self, session_id: str, data: str) -> None:
        pass

    @abstractmethod
    async def mark_end(self, session_id: str) -> None:
        pass

    @abstractmethod
    async def clear(self, session_id: str) -> None:
        pass

    @abstractmethod
    async def stream(
        self,
        session_id: str,
        generator: ContentStream,
        last_id: str = "0",
    ) -> AsyncGenerator[dict, None]:
        pass

    async def _wrap_generator(self, session_id: str, generator_fn: ContentStream):
        if isinstance(generator_fn, AsyncIterable):
            body_iterator = generator_fn
        else:
            body_iterator = iterate_in_threadpool(generator_fn)
        try:
            async for chunk in body_iterator:
                await self.push(session_id, chunk)
        finally:
            await self.mark_end(session_id)
            await self._set_state(session_id, self.end_marker)

    @abstractmethod
    async def _get_state(self, session_id: str) -> str:
        pass

    @abstractmethod
    async def _set_state(self, session_id: str, state: str) -> None:
        pass

    async def _should_generate(self, session_id: str) -> bool:
        state = await self._get_state(session_id)
        return state not in ("generating", self.end_marker)

    async def maybe_start_generator(
            self,
            session_id: str,
            generator: ContentStream,
    ):
        if generator and await self._should_generate(session_id):
            await self._set_state(session_id, "generating")
            asyncio.create_task(self._wrap_generator(session_id, generator))
            await asyncio.sleep(0.1)  # allow task to start