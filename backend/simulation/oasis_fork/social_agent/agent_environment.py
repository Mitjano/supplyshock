"""Agent environment — observation generators for social and commodity agents.

SocialEnvironment: formats posts as social media feed.
CommodityEnvironment: formats posts as market intelligence + live data.
"""

import logging
import sqlite3
from string import Template
from typing import Any

from ..social_platform.channel import ActionMessage, Channel
from ..social_platform.typing import ActionType

logger = logging.getLogger(__name__)


class SocialAction:
    """Proxy for agent to communicate with platform via channel."""

    def __init__(self, agent_id: int, channel: Channel):
        self.agent_id = agent_id
        self.channel = channel

    async def refresh(self) -> dict[str, Any]:
        """Request feed/market events from platform."""
        msg = ActionMessage(
            agent_id=self.agent_id,
            action=ActionType.REFRESH.value,
            args={},
        )
        return await self.channel.put(msg)

    async def execute(self, action: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute any action on the platform."""
        msg = ActionMessage(
            agent_id=self.agent_id,
            action=action,
            args=args,
        )
        return await self.channel.put(msg)


class SocialEnvironment:
    """Standard OASIS environment — presents social media feed."""

    def __init__(self, action: SocialAction):
        self.action = action

    async def to_text_prompt(self) -> str:
        """Generate observation string for the agent."""
        result = await self.action.refresh()
        if result.get("success") and result.get("posts"):
            posts = result["posts"]
            lines = []
            for p in posts:
                content = p.get("content", "")
                if content:
                    lines.append(f"- {content}")
            return "Recent posts:\n" + "\n".join(lines) if lines else "No new posts."
        return "No new posts."


class CommodityEnvironment(SocialEnvironment):
    """Environment observation for commodity market agents.

    Combines 4 data sources into a single observation prompt:
    1. Simulation events (from OASIS posts / ManualAction seeds)
    2. Live commodity prices (from TimescaleDB via toolkits)
    3. Live alerts & news (from GDELT via toolkits)
    4. Agent consensus prices (from simulation SQLite)
    """

    market_env_template = Template(
        "## CURRENT MARKET INTELLIGENCE\n"
        "$market_events\n\n"
        "$live_prices"
        "$live_alerts"
        "## AGENT MARKET CONSENSUS\n"
        "$market_state\n\n"
        "Based on this intelligence, decide your next action. "
        "Use the JSON response format from your instructions."
    )

    def __init__(
        self,
        action: SocialAction,
        db_path: str | None = None,
        commodity: str | None = None,
    ):
        super().__init__(action)
        self.db_path = db_path
        self.commodity = commodity

    async def to_text_prompt(self) -> str:
        """Generate market-focused observation string for the agent."""
        # 1. Simulation events (posts from OASIS platform)
        result = await self.action.refresh()
        if result.get("success") and result.get("posts"):
            events = []
            for p in result["posts"]:
                content = p.get("content", "")
                if content:
                    events.append(f"[EVENT] {content}")
            market_events = "\n".join(events) if events else "No new market events."
        else:
            market_events = "No new market events."

        # 2. Live prices from TimescaleDB (via toolkits)
        live_prices = self._get_live_prices()

        # 3. Live alerts from GDELT (via toolkits)
        live_alerts = self._get_live_alerts()

        # 4. Agent consensus from simulation SQLite
        market_state = self._get_market_state()

        return self.market_env_template.substitute(
            market_events=market_events,
            live_prices=live_prices,
            live_alerts=live_alerts,
            market_state=market_state,
        )

    def _get_live_prices(self) -> str:
        """Fetch live commodity prices from TimescaleDB via toolkits."""
        try:
            from ..commodity.toolkits import get_commodity_price

            # Fetch price for agent's primary commodity + key related ones
            commodities = ["coal", "crude_oil", "lng", "iron_ore"]
            if self.commodity and self.commodity not in commodities:
                commodities.insert(0, self.commodity)
            elif self.commodity:
                # Move agent's commodity to top
                commodities.remove(self.commodity)
                commodities.insert(0, self.commodity)

            lines = []
            for c in commodities:
                data = get_commodity_price(c)
                if "error" in data:
                    continue
                live_tag = "LIVE" if data.get("is_live") else "REF"
                change = data.get("change_1d_pct", 0)
                change_str = f" ({change:+.1f}%)" if change != 0 else ""
                lines.append(
                    f"  {c}: ${data['price_usd']}/{data['unit']} "
                    f"[{data.get('benchmark', '?')}]{change_str} [{live_tag}]"
                )

            if lines:
                return "## SPOT PRICES\n" + "\n".join(lines) + "\n\n"
            return ""
        except Exception as e:
            logger.debug("Live prices unavailable: %s", e)
            return ""

    def _get_live_alerts(self) -> str:
        """Fetch recent news/alerts from GDELT via toolkits."""
        try:
            from ..commodity.toolkits import get_recent_alerts

            commodity = self.commodity or "coal"
            data = get_recent_alerts(commodity, hours=48)

            if not data.get("alerts"):
                return ""

            lines = []
            for alert in data["alerts"][:5]:  # Max 5 alerts to keep prompt manageable
                severity = alert["severity"].upper()
                title = alert["title"][:150]
                source = alert.get("source", "unknown")
                lines.append(f"  [{severity}] {title} (via {source})")

            if lines:
                return "## RECENT NEWS & ALERTS\n" + "\n".join(lines) + "\n\n"
            return ""
        except Exception as e:
            logger.debug("Live alerts unavailable: %s", e)
            return ""

    def _get_market_state(self) -> str:
        """Read current price consensus from simulation's market_state table."""
        if not self.db_path:
            return "No price consensus established yet."
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT commodity,
                           ROUND(AVG(price_view), 2) as avg_price,
                           COUNT(*) as num_views,
                           ROUND(AVG(confidence), 2) as avg_confidence
                    FROM market_state
                    WHERE created_at > datetime('now', '-1 hour')
                    GROUP BY commodity
                    ORDER BY num_views DESC
                    LIMIT 10
                """)
                rows = cursor.fetchall()
            if not rows:
                return "No price consensus established yet."
            lines = [
                f"  {r[0]}: ${r[1]}/unit "
                f"(consensus from {r[2]} agents, confidence {r[3]:.0%})" if r[3] is not None
                else f"  {r[0]}: ${r[1]}/unit (consensus from {r[2]} agents)"
                for r in rows
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Market state unavailable: {e}"
