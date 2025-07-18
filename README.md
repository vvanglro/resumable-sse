# resumable-sse

> Asynchronous recoverable SSE (Server-Sent Events) push toolkit, supporting Redis and in-memory backend.

## ✨ Features

* ✅ Seamless integration with async generators (`async for`)
* 🔁 Resumable message stream support with `Last-Event-ID`
* 💾 Backend-agnostic: in-memory or Redis support
* ⚙️ Clean abstraction, minimal API surface
* 🧪 Easy to test, extendable for custom storage backends

## 🤔 Why Use `resumable-sse`?

In AI chat or streaming applications, when a user refreshes the page or the network is interrupted, the ongoing Server-Sent Events (SSE) stream is lost. Without a recovery mechanism, the frontend has no way to continue receiving the previous stream, and the backend often has to **re-generate the entire response**, wasting time and compute.

`resumable-sse` solves this by:

* Caching every message chunk in a backend (in-memory or Redis)
* Allowing clients to resume streaming from the last received event via `Last-Event-ID`
* Decoupling message generation from delivery, so you don’t have to re-trigger expensive operations

### 🧠 Use case example:

You’re building a web AI assistant. A user asks a long question. Halfway through the response, they accidentally refresh the browser. Instead of restarting the whole LLM generation, the backend resumes from where it left off and continues streaming seamlessly.

This avoids:

* Unnecessary re-generation
* Cost and latency from repeated model computation
* Poor user experience

## 📦 Installation

```bash
pip install resumable-sse
```

Or from source:

```bash
git clone https://github.com/vvanglro/resumable-sse.git
cd resumable-sse
pip install -e .
```

## 🚀 Quick Start

Using with FastAPI:

```python
import asyncio
from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse
from resumable_sse.factory import get_streamer

app = FastAPI()
streamer = get_streamer(backend="memory")

async def fake_generator():
    for word in ["Hello,", "I'm an AI.", "Nice to meet you."]:
        yield word
        await asyncio.sleep(1)

@app.get("/stream")
async def stream(request: Request, session_id: str):
    return EventSourceResponse(
        streamer.stream(session_id=session_id, generator=fake_generator())
    )
```

Supports resume with:

```http
GET /stream?session_id=abc
```

## 🔌 Redis Backend Example

```python
import redis.asyncio as redis
from resumable_sse.factory import get_streamer

redis_client = redis.Redis()
streamer = get_streamer(backend="redis", redis_client=redis_client)
```

## 📘 API Reference

```python
async def stream(
    self,
    session_id: str,
    generator: ContentStream,
    last_id: str = "0",
) -> AsyncGenerator[dict, None]:
```

* `session_id`: Unique ID per conversation or stream session
* `last_id`: Resume position (used with `Last-Event-ID`)
* `generator`: Async generator function that yields message chunks

## 🧪 Run Tests

```bash
pytest tests/
```

## 📁 Project Structure

```
resumable_sse/
├── base.py           # Abstract base class
├── memory.py         # In-memory implementation
├── redis.py          # Redis implementation
├── factory.py        # Factory for backend selection
├── __init__.py
README.md
pyproject.toml
```

## 📄 License

MIT License

---
