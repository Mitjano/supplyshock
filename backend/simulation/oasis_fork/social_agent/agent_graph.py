"""Agent graph — registry of all agents in a simulation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from .agent import SocialAgent

logger = logging.getLogger(__name__)


class AgentGraph:
    """Registry that holds all agents participating in a simulation."""

    def __init__(self):
        self._agents: dict[int, SocialAgent] = {}

    def add_agent(self, agent: SocialAgent) -> None:
        """Register an agent by its ID."""
        self._agents[agent.agent_id] = agent

    def get_agent(self, agent_id: int) -> SocialAgent | None:
        return self._agents.get(agent_id)

    def get_agents(self) -> Iterator[tuple[int, SocialAgent]]:
        """Yield (agent_id, agent) pairs."""
        yield from self._agents.items()

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, agent_id: int) -> bool:
        return agent_id in self._agents
