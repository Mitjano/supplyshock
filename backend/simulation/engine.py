"""Multi-agent simulation engine — orchestrates OASIS commodity fork.

Bridges the OASIS fork (AgentGraph, OasisEnv, ClaudeModel) to the Celery
task pipeline. Produces results in the same JSON schema as the deterministic
model so the frontend works unchanged.

Usage (from Celery task):
    engine = SimulationEngine(sim_config, db_url, api_key, publish_progress)
    result = await engine.run()
    # result has same shape as deterministic model output
"""

import asyncio
import logging
import math
import os
import sqlite3
import tempfile
import time
from typing import Any, Callable, Optional

from .oasis_fork import ActionType, AgentGraph, LLMAction, ManualAction, OasisEnv
from .oasis_fork.social_platform.typing import DefaultPlatformType
from .oasis_fork.social_platform.config.user import CommodityAgentInfo
from .oasis_fork.social_agent.agent import SocialAgent
from .oasis_fork.commodity.agents import (
    make_coal_trader,
    make_bulk_shipper,
    make_government_agent,
    make_refinery,
)
from .oasis_fork.commodity.market import compute_consensus_price, get_simulation_summary
from .oasis_fork.model import ClaudeModel

logger = logging.getLogger("simulation.engine")

# Seed event templates per event type
_SEED_TEMPLATES: dict[str, str] = {
    "flood": (
        "BREAKING MARKET ALERT: Major flooding at {node_name}. "
        "Infrastructure severely damaged, throughput reduced by {intensity_pct}%. "
        "Estimated disruption: {duration_weeks} weeks minimum. "
        "Affected commodities: {commodities}. "
        "Current baseline spot prices: {prices_str}. "
        "Alternative supply sources may see increased demand."
    ),
    "strike": (
        "MARKET ALERT: Workers at {node_name} have begun an indefinite strike. "
        "Port/facility operations reduced by {intensity_pct}%. "
        "Duration estimate: {duration_weeks} weeks. "
        "Affected commodities: {commodities}. Baseline: {prices_str}."
    ),
    "blockade": (
        "CRITICAL ALERT: Naval blockade affecting {node_name}. "
        "Commercial traffic restricted — capacity down {intensity_pct}%. "
        "Duration unclear, minimum {duration_weeks} weeks expected. "
        "Commodities affected: {commodities}. Baseline: {prices_str}."
    ),
    "storm": (
        "WEATHER ALERT: Severe storm system impacting {node_name}. "
        "Operations suspended, throughput down {intensity_pct}%. "
        "Forecast: {duration_weeks} weeks of disruption. "
        "Affected: {commodities}. Baseline: {prices_str}."
    ),
    "earthquake": (
        "EMERGENCY: Earthquake near {node_name}. "
        "Major structural damage, capacity reduced by {intensity_pct}%. "
        "Recovery estimate: {duration_weeks}+ weeks. "
        "Affected commodities: {commodities}. Baseline: {prices_str}."
    ),
    "war": (
        "CRITICAL GEOPOLITICAL ALERT: Armed conflict affecting {node_name}. "
        "All commercial operations halted — effective capacity loss {intensity_pct}%. "
        "No timeline for resolution, minimum {duration_weeks} weeks. "
        "Commodities: {commodities}. Baseline: {prices_str}."
    ),
    "sanctions": (
        "REGULATORY ALERT: New sanctions regime targeting {node_name}. "
        "Trade volumes expected to drop {intensity_pct}%. "
        "Duration: {duration_weeks}+ weeks (policy-dependent). "
        "Commodities affected: {commodities}. Baseline: {prices_str}."
    ),
    "drought": (
        "CLIMATE ALERT: Severe drought affecting operations at {node_name}. "
        "Waterway/port capacity reduced by {intensity_pct}%. "
        "Expected duration: {duration_weeks} weeks. "
        "Commodities: {commodities}. Baseline: {prices_str}."
    ),
    "pandemic": (
        "HEALTH ALERT: Pandemic-related restrictions at {node_name}. "
        "Workforce reduced, throughput down {intensity_pct}%. "
        "Duration: {duration_weeks}+ weeks. "
        "Commodities: {commodities}. Baseline: {prices_str}."
    ),
}


class SimulationEngine:
    """Orchestrates OASIS multi-agent commodity simulation.

    Creates a mix of LLM-driven and rule-based agents, injects a disruption
    seed event, runs decision rounds, and extracts consensus-based predictions.
    """

    def __init__(
        self,
        sim_config: dict[str, Any],
        baseline_prices: dict[str, dict],
        node_info: tuple,
        db_url_sync: str,
        claude_api_key: str,
        publish_progress: Callable[[int, str], None],
    ):
        """
        Args:
            sim_config: Dict with keys: node, node_name, event_type,
                duration_weeks, intensity, horizon_days, agents_count,
                affected_commodities, global_share_pct.
            baseline_prices: {commodity: {benchmark, price}} from TimescaleDB.
            node_info: (name, global_share_pct, baseline_risk, annual_volume_mt).
            db_url_sync: PostgreSQL sync connection string for live data.
            claude_api_key: Anthropic API key for LLM agents.
            publish_progress: Callback(progress_pct, log_line).
        """
        self.config = sim_config
        self.baseline_prices = baseline_prices
        self.node_info = node_info
        self.db_url_sync = db_url_sync
        self.claude_api_key = claude_api_key
        self.publish = publish_progress

        self._sqlite_path = os.path.join(
            tempfile.gettempdir(),
            f"oasis_sim_{sim_config.get('simulation_id', 'tmp')}.db",
        )
        self._env: Optional[OasisEnv] = None
        self._graph: Optional[AgentGraph] = None

    def _build_agents(self) -> AgentGraph:
        """Create agent graph with appropriate mix of LLM and rule-based agents."""
        graph = AgentGraph()
        agents_count = self.config.get("agents_count", 50)
        primary_commodity = "coal"
        commodities = self.config.get("affected_commodities", ["coal"])
        if commodities:
            primary_commodity = commodities[0]

        # LLM model — Haiku for cost efficiency (~$0.001 per decision)
        haiku = ClaudeModel(
            model_id="claude-haiku-4-5-20251001",
            api_key=self.claude_api_key,
            max_tokens=256,
            temperature=0.7,
            timeout=30.0,
        )

        # Agent distribution: ~20% LLM traders, ~5% LLM govt, ~75% rule-based
        n_llm_traders = max(3, min(15, agents_count // 5))
        n_llm_govt = max(1, min(4, agents_count // 20))
        n_rule_based = agents_count - n_llm_traders - n_llm_govt

        agent_id = 0

        # LLM traders — spread across importer regions
        regions = ["JP", "CN", "KR", "DE"]
        for i in range(n_llm_traders):
            region = regions[i % len(regions)]
            risk = ["low", "medium", "high"][i % 3]
            make_coal_trader(agent_id, graph, haiku, region=region, risk_tolerance=risk)
            agent_id += 1

        # LLM government agents — source and destination countries
        govt_countries = ["AU", "CN", "JP", "DE"]
        for i in range(n_llm_govt):
            country = govt_countries[i % len(govt_countries)]
            make_government_agent(agent_id, graph, haiku, country=country)
            agent_id += 1

        # Rule-based agents — refineries and passive shippers (zero LLM cost)
        n_refineries = n_rule_based // 3
        n_shippers = n_rule_based - n_refineries

        for i in range(n_refineries):
            commodity = commodities[i % len(commodities)] if commodities else primary_commodity
            make_refinery(agent_id, graph, commodity=commodity, inventory_days=30 + (i % 4) * 10)
            agent_id += 1

        for i in range(n_shippers):
            agent = SocialAgent(
                agent_id=agent_id,
                user_info=CommodityAgentInfo(
                    user_name=f"shipper_{agent_id}",
                    agent_type="shipper",
                    commodity=primary_commodity,
                    description="Bulk carrier operator on major trade routes.",
                ),
                agent_graph=graph,
                model=None,
                available_actions=[ActionType.DO_NOTHING],
            )
            graph.add_agent(agent)
            agent_id += 1

        self.publish(
            15,
            f"Created {len(graph)} agents: "
            f"{n_llm_traders} LLM traders, {n_llm_govt} govt, "
            f"{n_refineries} refineries, {n_shippers} shippers",
        )
        return graph

    def _build_seed_event(self) -> str:
        """Generate disruption seed event text from simulation config."""
        event_type = self.config.get("event_type", "flood")
        template = _SEED_TEMPLATES.get(event_type, _SEED_TEMPLATES["flood"])

        prices_parts = []
        for commodity, bp in self.baseline_prices.items():
            prices_parts.append(f"{commodity}: ${bp['price']}")

        return template.format(
            node_name=self.config.get("node_name", self.config.get("node", "Unknown")),
            intensity_pct=int(self.config.get("intensity", 0.7) * 100),
            duration_weeks=self.config.get("duration_weeks", 4),
            commodities=", ".join(self.config.get("affected_commodities", ["coal"])),
            prices_str=", ".join(prices_parts) if prices_parts else "N/A",
        )

    async def _inject_gdelt_alerts(self, all_agents: list) -> int:
        """Inject recent GDELT news alerts as ManualAction CREATE_POST events.

        Returns number of alerts injected (0 if live data unavailable).
        """
        try:
            from .oasis_fork.commodity.toolkits import get_recent_alerts

            commodities = self.config.get("affected_commodities", ["coal"])
            injected = 0

            for commodity in commodities[:2]:  # Max 2 commodities to limit noise
                data = get_recent_alerts(commodity, hours=72)
                alerts = data.get("alerts", [])

                for alert in alerts[:3]:  # Max 3 alerts per commodity
                    severity = alert.get("severity", "info").upper()
                    title = alert.get("title", "")
                    source = alert.get("source", "unknown")
                    if not title:
                        continue

                    content = f"[{severity} — {source}] {title}"

                    poster = all_agents[min(injected + 1, len(all_agents) - 1)][1]
                    await self._env.step({
                        poster: ManualAction(
                            action_type=ActionType.CREATE_POST,
                            action_args={"content": content},
                        )
                    })
                    injected += 1

            return injected
        except Exception as e:
            logger.debug("GDELT injection skipped: %s", e)
            return 0

    async def run(self) -> dict[str, Any]:
        """Execute the full multi-agent simulation.

        Returns:
            dict: Same schema as deterministic model — predictions, risk_score, etc.
        """
        start_time = time.time()

        # 1. Build agent graph
        self.publish(10, "Building agent graph")
        self._graph = self._build_agents()

        # 2. Initialize OASIS environment
        self.publish(20, "Initializing OASIS environment")
        self._env = OasisEnv(
            agent_graph=self._graph,
            platform=DefaultPlatformType.COMMODITY,
            database_path=self._sqlite_path,
            semaphore=10,
            live_db_url=self.db_url_sync,
        )
        await self._env.reset()

        # 3. Inject seed disruption event
        self.publish(25, "Injecting disruption seed event")
        all_agents = list(self._graph.get_agents())
        seed_agent = all_agents[0][1]
        seed_content = self._build_seed_event()

        await self._env.step({
            seed_agent: ManualAction(
                action_type=ActionType.CREATE_POST,
                action_args={"content": seed_content},
            )
        })

        # 3b. Inject recent GDELT alerts as additional context events
        gdelt_injected = await self._inject_gdelt_alerts(all_agents)
        if gdelt_injected > 0:
            self.publish(27, f"Injected {gdelt_injected} real-time news alerts")

        # 4. Run simulation steps
        # Map horizon to steps: ~1 step per simulated week, max 10 steps
        horizon_days = self.config.get("horizon_days", 90)
        n_steps = min(10, max(3, horizon_days // 14))

        llm_agents = [(aid, a) for aid, a in all_agents if a.model is not None]
        rule_agents = [(aid, a) for aid, a in all_agents if a.model is None]

        consensus_history: list[dict[str, Optional[float]]] = []
        commodities = self.config.get("affected_commodities", ["coal"])

        for step in range(1, n_steps + 1):
            progress = 25 + int(60 * step / n_steps)
            self.publish(min(progress, 85), f"Step {step}/{n_steps}: agents deciding")

            os.environ["OASIS_SIM_STEP"] = str(step)

            actions = {}
            for _, agent in llm_agents:
                actions[agent] = LLMAction()
            for _, agent in rule_agents:
                actions[agent] = ManualAction(
                    action_type=ActionType.DO_NOTHING,
                    action_args={},
                )

            await self._env.step(actions)

            # Record consensus prices after each step
            step_consensus = {}
            for commodity in commodities:
                price = compute_consensus_price(commodity, self._sqlite_path, last_n_steps=1)
                step_consensus[commodity] = price
            consensus_history.append(step_consensus)

        # 5. Close environment
        await self._env.close()
        elapsed = time.time() - start_time
        self.publish(90, f"Simulation completed in {elapsed:.1f}s, building results")

        # 6. Extract results and format to match deterministic schema
        result = self._build_result(consensus_history, n_steps, elapsed)
        self.publish(95, "Results ready")
        return result

    def _build_result(
        self,
        consensus_history: list[dict[str, Optional[float]]],
        n_steps: int,
        elapsed: float,
    ) -> dict[str, Any]:
        """Convert OASIS agent decisions into the deterministic result format.

        Maps consensus price history to weekly_prices array, computes peak impact,
        and estimates recovery — same JSON shape as tasks.py deterministic model.
        """
        node = self.config.get("node", "unknown")
        node_name = self.config.get("node_name", node)
        event_type = self.config.get("event_type", "flood")
        duration_weeks = self.config.get("duration_weeks", 4)
        intensity = self.config.get("intensity", 0.7)
        horizon_days = self.config.get("horizon_days", 90)
        global_share = self.config.get("global_share_pct", 10.0)
        base_risk = self.node_info[2] if self.node_info else 5
        commodities = self.config.get("affected_commodities", ["coal"])

        # Event multipliers (same as deterministic for risk_score consistency)
        event_multipliers = {
            "flood": 1.2, "strike": 0.8, "blockade": 1.5,
            "storm": 1.0, "earthquake": 1.8, "war": 2.0,
            "sanctions": 1.3, "drought": 0.9, "pandemic": 0.7,
        }
        event_mult = event_multipliers.get(event_type, 1.0)

        # Build predictions per commodity
        total_weeks = horizon_days // 7
        predictions = {}

        for commodity in commodities:
            bp = self.baseline_prices.get(commodity, {})
            baseline_price = bp.get("price", 100.0)
            benchmark = bp.get("benchmark", "Unknown")

            # Extract consensus prices from history (one per OASIS step)
            agent_prices = []
            for step_data in consensus_history:
                p = step_data.get(commodity)
                if p is not None and p > 0:
                    agent_prices.append(p)

            if not agent_prices:
                # Agents didn't produce price views for this commodity — skip
                agent_prices = [baseline_price]

            # Interpolate agent consensus prices to weekly timeline
            weekly_prices = self._interpolate_to_weekly(
                agent_prices, baseline_price, total_weeks, duration_weeks,
            )

            peak_price = max(weekly_prices)
            peak_change_pct = round((peak_price - baseline_price) / baseline_price * 100, 1)

            # Estimate recovery week (when price returns within 5% of baseline)
            recovery_week = 0
            if peak_change_pct > 0:
                for i, p in enumerate(weekly_prices):
                    if i > 0 and abs(p - baseline_price) / baseline_price < 0.05:
                        recovery_week = i + 1
                        break
                if recovery_week == 0:
                    # Still elevated at end — estimate via log decay
                    recovery_week = duration_weeks + int(math.log(0.05) / (-0.15))

            predictions[commodity] = {
                "benchmark": benchmark,
                "baseline_price": baseline_price,
                "weekly_prices": weekly_prices,
                "peak_price": peak_price,
                "peak_change_pct": peak_change_pct,
                "recovery_week": recovery_week,
            }

        # Simulation summary from OASIS SQLite
        summary_data = get_simulation_summary(self._sqlite_path)

        # Build result in same shape as deterministic model
        max_impact = max(
            (p["peak_change_pct"] for p in predictions.values()), default=0,
        )
        result = {
            "node": node,
            "node_name": node_name,
            "event_type": event_type,
            "duration_weeks": duration_weeks,
            "intensity": intensity,
            "horizon_days": horizon_days,
            "global_share_pct": global_share,
            "predictions": predictions,
            "risk_score": round(min(10, base_risk * intensity * event_mult), 1),
            "summary": (
                f"{'High' if intensity > 0.7 else 'Moderate'} disruption at {node_name}. "
                f"Multi-agent simulation ({len(list(self._graph.get_agents()))} agents, "
                f"{n_steps} rounds) predicts peak commodity impact of {max_impact:.1f}%."
            ),
            # Extra fields for OASIS-specific results
            "simulation_type": "multi_agent",
            "agent_count": len(list(self._graph.get_agents())),
            "steps": n_steps,
            "elapsed_seconds": round(elapsed, 1),
            "agent_summary": {
                "trade_distribution": summary_data.get("trade_counts", []),
                "reroute_patterns": summary_data.get("reroutes", []),
                "government_measures": summary_data.get("measures", []),
            },
        }

        # Cleanup temp SQLite
        try:
            os.remove(self._sqlite_path)
        except OSError:
            pass

        return result

    @staticmethod
    def _interpolate_to_weekly(
        agent_prices: list[float],
        baseline: float,
        total_weeks: int,
        duration_weeks: int,
    ) -> list[float]:
        """Interpolate sparse agent consensus prices to full weekly timeline.

        Agent steps are spread evenly across the disruption period.
        After disruption, prices decay back toward baseline (recovery phase).
        """
        weekly = []
        n_agent = len(agent_prices)

        for week in range(1, total_weeks + 1):
            if week <= duration_weeks and n_agent > 0:
                # Disruption phase — interpolate from agent consensus prices
                # Map week (1..duration_weeks) to agent_prices index
                ratio = (week - 1) / max(duration_weeks - 1, 1)
                idx_float = ratio * (n_agent - 1)
                idx_low = int(idx_float)
                idx_high = min(idx_low + 1, n_agent - 1)
                frac = idx_float - idx_low

                price = agent_prices[idx_low] * (1 - frac) + agent_prices[idx_high] * frac
            else:
                # Recovery phase — exponential decay from last disruption price
                last_disruption = weekly[-1] if weekly else agent_prices[-1]
                recovery_week = week - duration_weeks
                recovery_rate = 0.15
                remaining = (last_disruption - baseline) * math.exp(-recovery_rate * recovery_week)
                price = baseline + remaining

            weekly.append(round(price, 2))

        return weekly
