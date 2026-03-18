"""AI Chat Engine — streams Claude responses with live supply chain context.

Uses real DB data (commodity prices, alerts, port congestion, voyages)
to ground Claude's answers in actual platform state.
"""

import logging
from typing import AsyncGenerator

import anthropic
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are SupplyShock AI, a supply chain intelligence assistant. "
    "Answer based on the data context provided. Be concise and data-driven. "
    "When referencing data, cite specific numbers. "
    "If the context doesn't contain relevant information, say so honestly. "
    "Format responses with markdown when helpful."
)

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024


async def _build_context(db: AsyncSession) -> str:
    """Query live platform data to build context for the AI."""
    sections: list[str] = []

    # Recent commodity prices (top 5 by absolute change)
    try:
        result = await db.execute(text("""
            SELECT symbol, name, price_usd, change_pct_24h
            FROM commodity_prices
            ORDER BY ABS(change_pct_24h) DESC NULLS LAST
            LIMIT 5
        """))
        rows = result.mappings().all()
        if rows:
            lines = ["## Recent Commodity Prices (top movers)"]
            for r in rows:
                change = r["change_pct_24h"] or 0
                lines.append(f"- {r['name']} ({r['symbol']}): ${r['price_usd']:.2f} ({change:+.2f}%)")
            sections.append("\n".join(lines))
    except Exception as e:
        logger.debug("Skipping commodity prices context: %s", e)

    # Active alerts (last 24h, top 5)
    try:
        result = await db.execute(text("""
            SELECT title, severity, commodity, type
            FROM alert_events
            WHERE time > NOW() - INTERVAL '24 hours'
              AND is_active = TRUE
            ORDER BY time DESC
            LIMIT 5
        """))
        rows = result.mappings().all()
        if rows:
            lines = ["## Active Alerts (last 24h)"]
            for r in rows:
                lines.append(f"- [{r['severity'].upper()}] {r['title']} (commodity: {r['commodity'] or 'N/A'}, type: {r['type']})")
            sections.append("\n".join(lines))
    except Exception as e:
        logger.debug("Skipping alerts context: %s", e)

    # Port congestion (top 5)
    try:
        result = await db.execute(text("""
            SELECT bn.name, bn.region, bn.congestion_pct, bn.risk_level
            FROM bottleneck_nodes bn
            WHERE bn.congestion_pct IS NOT NULL
            ORDER BY bn.congestion_pct DESC
            LIMIT 5
        """))
        rows = result.mappings().all()
        if rows:
            lines = ["## Port / Chokepoint Congestion"]
            for r in rows:
                lines.append(f"- {r['name']} ({r['region']}): {r['congestion_pct']:.0f}% congestion, risk: {r['risk_level']}")
            sections.append("\n".join(lines))
    except Exception as e:
        logger.debug("Skipping port congestion context: %s", e)

    # Active voyages count
    try:
        result = await db.execute(text("""
            SELECT COUNT(*) as cnt FROM voyages WHERE status = 'underway'
        """))
        count = result.scalar() or 0
        sections.append(f"## Vessel Activity\n- Active voyages underway: {count}")
    except Exception as e:
        logger.debug("Skipping voyages context: %s", e)

    if not sections:
        return "No live data available at this moment."

    return "\n\n".join(sections)


class ChatEngine:
    """Streams AI chat responses grounded in live supply chain data."""

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.CLAUDE_API_KEY)

    async def chat(
        self,
        question: str,
        user_plan: str,
        db: AsyncSession,
    ) -> AsyncGenerator[str, None]:
        """Stream Claude response tokens for a user question.

        Yields text chunks as they arrive from the API.
        """
        context = await _build_context(db)

        user_message = (
            f"<context>\n{context}\n</context>\n\n"
            f"User question: {question}"
        )

        async with self.client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            async for chunk in stream.text_stream:
                yield chunk
