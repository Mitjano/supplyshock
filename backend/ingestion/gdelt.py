"""GDELT news watcher — monitors global news for commodity supply chain disruptions.

Polls GDELT GKG API every 15 minutes, classifies events by commodity and severity,
deduplicates by source_url, and inserts into alert_events table.
"""

import json
import logging
import re
from datetime import datetime, timezone

import httpx
import psycopg2
from psycopg2.extras import execute_values

from config import settings

logger = logging.getLogger(__name__)

GDELT_GKG_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Keywords that map to commodities
COMMODITY_KEYWORDS = {
    "crude_oil": ["oil price", "crude oil", "petroleum", "OPEC", "oil supply", "oil embargo", "oil pipeline", "refinery"],
    "coal": ["coal mine", "coal price", "coal export", "thermal coal", "coal supply"],
    "iron_ore": ["iron ore", "steel production", "iron ore price", "mining"],
    "copper": ["copper price", "copper mine", "copper supply", "copper shortage"],
    "lng": ["LNG", "natural gas", "gas pipeline", "gas supply", "liquefied natural gas"],
}

# Regions/locations that indicate supply chain relevance
SUPPLY_CHAIN_KEYWORDS = [
    "supply chain", "disruption", "shortage", "embargo", "sanctions",
    "port closure", "strike", "blockade", "chokepoint", "strait",
    "Suez", "Hormuz", "Malacca", "Panama Canal", "pipeline",
    "explosion", "earthquake", "hurricane", "typhoon", "flood",
]

# GDELT tone score → severity mapping
# tone < -5 = critical, -5 to -2 = warning, > -2 = info
TONE_THRESHOLDS = {"critical": -5.0, "warning": -2.0}


def _classify_commodity(text: str) -> str | None:
    """Match article text to a commodity type."""
    text_lower = text.lower()
    for commodity, keywords in COMMODITY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                return commodity
    return None


def _classify_severity(tone: float) -> str:
    """Map GDELT tone score to severity level."""
    if tone < TONE_THRESHOLDS["critical"]:
        return "critical"
    elif tone < TONE_THRESHOLDS["warning"]:
        return "warning"
    return "info"


def _is_supply_chain_relevant(text: str) -> bool:
    """Check if article mentions supply chain disruption keywords."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in SUPPLY_CHAIN_KEYWORDS)


def fetch_gdelt_articles() -> list[dict]:
    """Fetch recent commodity-related articles from GDELT."""
    query = " OR ".join([
        "crude oil supply",
        "coal export",
        "iron ore shipment",
        "copper mine",
        "LNG supply",
        "commodity disruption",
        "port closure",
        "supply chain crisis",
    ])

    try:
        resp = httpx.get(
            GDELT_GKG_URL,
            params={
                "query": query,
                "mode": "ArtList",
                "maxrecords": 50,
                "format": "json",
                "timespan": "15min",
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("GDELT fetch failed: %s", e)
        return []

    articles = data.get("articles", [])
    events = []

    for article in articles:
        title = article.get("title", "")
        url = article.get("url", "")
        tone = article.get("tone", 0)
        seendate = article.get("seendate", "")

        if not title or not url:
            continue

        # Classify commodity
        commodity = _classify_commodity(title)
        if not commodity and not _is_supply_chain_relevant(title):
            continue

        severity = _classify_severity(float(tone) if tone else 0)

        events.append({
            "type": "news_event",
            "severity": severity,
            "commodity": commodity,
            "title": title[:500],
            "body": f"Source: {article.get('domain', 'unknown')}",
            "source": "gdelt",
            "source_url": url,
            "metadata": json.dumps({"tone": tone, "domain": article.get("domain")}),
            "time": datetime.now(timezone.utc).isoformat(),
        })

    return events


def ingest_gdelt_alerts():
    """Fetch GDELT articles and insert new alerts (dedup by source_url)."""
    events = fetch_gdelt_articles()
    if not events:
        logger.info("No new GDELT events found")
        return 0

    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    inserted = 0

    try:
        with conn.cursor() as cur:
            for event in events:
                # Dedup: skip if source_url already exists
                cur.execute(
                    "SELECT 1 FROM alert_events WHERE source_url = %s LIMIT 1",
                    (event["source_url"],),
                )
                if cur.fetchone():
                    continue

                cur.execute(
                    """
                    INSERT INTO alert_events (type, severity, commodity, title,
                        body, source, source_url, metadata, time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event["type"], event["severity"], event["commodity"],
                        event["title"], event["body"], event["source"],
                        event["source_url"], event["metadata"], event["time"],
                    ),
                )
                inserted += 1

        conn.commit()
        logger.info("Inserted %d new GDELT alerts (of %d fetched)", inserted, len(events))
    finally:
        conn.close()

    # Publish to Redis for SSE clients
    if inserted > 0:
        _publish_alerts(events[:inserted])

    return inserted


def _publish_alerts(events: list[dict]):
    """Publish new alerts to Redis pub/sub for SSE."""
    import redis as sync_redis

    try:
        r = sync_redis.from_url(settings.REDIS_URL)
        for event in events:
            r.publish("alerts", json.dumps(event))
        r.close()
    except Exception as e:
        logger.warning("Failed to publish alerts to Redis: %s", e)
