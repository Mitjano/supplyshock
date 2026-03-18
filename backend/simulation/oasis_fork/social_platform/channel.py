"""Async message channel between agents and platform.

Simplified version of OASIS Channel — agents put action requests,
platform processes them and returns results.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ActionMessage:
    """Message from agent to platform."""

    agent_id: int
    action: str  # ActionType.value
    args: dict[str, Any] = field(default_factory=dict)
    result_future: asyncio.Future | None = None


class Channel:
    """Async channel for agent ↔ platform communication."""

    def __init__(self):
        self._queue: asyncio.Queue[ActionMessage] = asyncio.Queue()
        self._results: dict[int, dict[str, Any]] = {}

    async def put(self, message: ActionMessage) -> dict[str, Any]:
        """Agent sends action to platform, waits for result."""
        loop = asyncio.get_running_loop()
        message.result_future = loop.create_future()
        await self._queue.put(message)
        return await message.result_future

    async def get(self) -> ActionMessage:
        """Platform reads next action from queue."""
        return await self._queue.get()

    def empty(self) -> bool:
        return self._queue.empty()

    def qsize(self) -> int:
        return self._queue.qsize()
