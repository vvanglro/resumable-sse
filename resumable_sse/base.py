import asyncio
import time
from typing import AsyncIterable, Iterator, Any, AsyncGenerator, AsyncIterator, TypeVar, Iterable
from abc import ABC, abstractmethod

from resumable_sse.state import ChatState

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
        await self.set_state(session_id, ChatState.GENERATING)
        try:
            async for chunk in body_iterator:
                await self.push(session_id, chunk)
        finally:
            await self.mark_end(session_id)
            await self.set_state(session_id, self.end_marker)
            await self._clear(session_id)

    @abstractmethod
    async def get_state(self, session_id: str) -> str:
        pass

    @abstractmethod
    async def set_state(self, session_id: str, state: str) -> None:
        pass

    @abstractmethod
    async def check_generation_limit(self, state: str, session_id: str) -> bool:
        pass

    async def _clear(self, session_id: str) -> None:
        st = time.time()
        # If the message is not normally received by the front-end within 10 seconds after it is generated, it will be cleared.
        while await self.get_state(session_id) != ChatState.DONE and time.time() - st < 10:
            await asyncio.sleep(1)
        await self.clear(session_id)

    async def _should_generate(self, state: str) -> bool:
        return state not in (ChatState.START, ChatState.GENERATING, self.end_marker)

    async def maybe_start_generator(
            self,
            session_id: str,
            generator: ContentStream,
    ) -> bool:
        state = await self.get_state(session_id)
        if not await self.check_generation_limit(state, session_id):
            return False

        if generator and await self._should_generate(state):
            await self.set_state(session_id, ChatState.START)
            asyncio.create_task(self._wrap_generator(session_id, generator))
            await asyncio.sleep(0.1)  # allow task to start

        return True
