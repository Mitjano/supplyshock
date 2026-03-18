"""OasisEnv — the simulation orchestrator.

Manages the Platform, Channel, and steps through the simulation.
Each step: agents observe → decide (LLM or manual) → platform executes.
"""

import asyncio
import logging
import os
from typing import Any

from ..social_agent.agent import SocialAgent
from ..social_agent.agent_action import LLMAction, ManualAction
from ..social_agent.agent_graph import AgentGraph
from ..social_platform.channel import ActionMessage, Channel
from ..social_platform.platform import Platform
from ..social_platform.typing import ActionType, DefaultPlatformType

logger = logging.getLogger(__name__)


class OasisEnv:
    """Top-level simulation environment.

    Usage:
        env = OasisEnv(agent_graph, DefaultPlatformType.COMMODITY, db_path)
        await env.reset()
        await env.step(actions_dict)   # repeat for N steps
        await env.close()
    """

    def __init__(
        self,
        agent_graph: AgentGraph,
        platform: DefaultPlatformType = DefaultPlatformType.COMMODITY,
        database_path: str = "/tmp/oasis_sim.db",
        semaphore: int = 10,
        live_db_url: str | None = None,
    ):
        self.agent_graph = agent_graph
        self.platform_type = platform
        self.database_path = database_path
        self.semaphore = asyncio.Semaphore(semaphore)
        self.live_db_url = live_db_url

        self.channel = Channel()
        self.platform: Platform | None = None
        self._step_count = 0
        self._live_data_connected = False

    async def reset(self) -> None:
        """Initialize platform, connect live data, and register all agents."""
        # Connect to TimescaleDB for live market data (if URL provided)
        if self.live_db_url:
            from ..commodity.toolkits import init_live_data
            self._live_data_connected = init_live_data(self.live_db_url)
            if self._live_data_connected:
                logger.info("Live market data connected — agents will see real prices/alerts")
            else:
                logger.warning("Live data connection failed — using baseline fallback")

        # Remove old simulation database if exists
        if os.path.exists(self.database_path):
            os.remove(self.database_path)

        # Configure platform based on type
        if self.platform_type == DefaultPlatformType.COMMODITY:
            self.platform = Platform(
                db_path=self.database_path,
                channel=self.channel,
                max_rec_post_len=50,
                refresh_rec_post_count=10,
            )
        else:
            self.platform = Platform(
                db_path=self.database_path,
                channel=self.channel,
                max_rec_post_len=20,
                refresh_rec_post_count=5,
            )

        # Start platform processing loop
        await self.platform.start()

        # Setup all agents with channel reference
        for agent_id, agent in self.agent_graph.get_agents():
            agent.setup(self.channel, db_path=self.database_path)

        # Register all agents in database
        for agent_id, agent in self.agent_graph.get_agents():
            user_name = getattr(agent.user_info, "user_name", f"agent_{agent_id}")
            msg = ActionMessage(
                agent_id=agent_id,
                action=ActionType.SIGN_UP.value,
                args={"user_name": user_name},
            )
            await self.channel.put(msg)

        self._step_count = 0
        logger.info(
            "OasisEnv reset: %d agents, platform=%s, db=%s",
            len(self.agent_graph),
            self.platform_type.value,
            self.database_path,
        )

    async def step(
        self, actions: dict[SocialAgent, LLMAction | ManualAction]
    ) -> None:
        """Execute one simulation step.

        Args:
            actions: Dict mapping agent → action for this step.
                LLMAction: agent observes env, LLM decides.
                ManualAction: pre-scripted action executed directly.
        """
        self._step_count += 1
        os.environ["OASIS_SIM_STEP"] = str(self._step_count)

        tasks = []
        for agent, action in actions.items():
            tasks.append(self._execute_agent_action(agent, action))

        # Run all agent actions concurrently (bounded by semaphore)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                agent = list(actions.keys())[i]
                logger.error(
                    "Step %d agent %d error: %s",
                    self._step_count, agent.agent_id, result,
                )

    async def _execute_agent_action(
        self, agent: SocialAgent, action: LLMAction | ManualAction
    ) -> dict[str, Any]:
        """Execute a single agent's action for this step."""
        async with self.semaphore:
            if isinstance(action, ManualAction):
                # Direct action — no LLM call
                msg = ActionMessage(
                    agent_id=agent.agent_id,
                    action=action.action_type.value,
                    args=action.action_args,
                )
                return await self.channel.put(msg)

            elif isinstance(action, LLMAction):
                # LLM-driven decision
                observation = await agent.observe()
                action_type, action_args = await agent.decide(observation)

                msg = ActionMessage(
                    agent_id=agent.agent_id,
                    action=action_type.value,
                    args=action_args,
                )
                return await self.channel.put(msg)

            else:
                logger.warning(
                    "Unknown action type for agent %d: %s",
                    agent.agent_id, type(action),
                )
                return {"success": False, "error": "Unknown action type"}

    async def close(self) -> None:
        """Shutdown platform and cleanup."""
        if self.platform:
            await self.platform.stop()

        # Close live data connection
        if self._live_data_connected:
            from ..commodity.toolkits import close_live_data
            close_live_data()

        logger.info(
            "OasisEnv closed after %d steps (live_data=%s).",
            self._step_count, self._live_data_connected,
        )
