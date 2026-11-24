"""Request-scoped transport for the existing tailor/preview/confirm pipeline."""

import asyncio
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

from app.ai_budget import remaining_timeout

job: ContextVar[str | None] = ContextVar("t3_tailoring_job", default=None)


@contextmanager
def for_job(job_id: str) -> Iterator[None]:
    token = job.set(job_id if os.getenv("RESUME_T3_SOCKET") else None)
    try:
        yield
    finally:
        job.reset(token)


async def completion(messages: list[dict[str, Any]]) -> SimpleNamespace:
    async with asyncio.timeout(remaining_timeout()):
        reader, writer = await asyncio.open_unix_connection(
            os.environ["RESUME_T3_SOCKET"], limit=2000000
        )
        try:
            writer.write(
                json.dumps({"job": job.get(), "messages": messages}).encode() + b"\n"
            )
            await writer.drain()
            result = json.loads(await reader.readline())
        finally:
            writer.close()
            await writer.wait_closed()
    if not result.get("ok"):
        raise ValueError("T3 could not finish this generation step")
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=result["reply"]), finish_reason="stop"
            )
        ]
    )
