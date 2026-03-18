"""GDELT GKG news watcher — supply chain alert generation.

Polls GDELT Global Knowledge Graph API every 15 minutes.
Classifies events by commodity and severity.
Deduplicates by source_url to avoid repeat alerts.

Called by Celery beat task `ingest_gdelt_alerts`.
"""

import json
import logging
from datetime import datetime, timezone

import psycopg2
import requests

from config import settings

logger = logging.getLogger("gdelt")

GDELT_GKG_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# Keywords mapped to commodities
COMMODITY_KEYWORDS: dict[str, list[str]] = {
    "crude_oil": [
        "crude oil", "oil price", "oil supply", "OPEC", "petroleum",
        "oil pipeline", "oil tanker", "refinery", "oil export",
        "Brent crude", "WTI crude", "oil production",
    ],
    "lng": [
        "LNG", "liquefied natural gas", "natural gas", "gas pipeline",
        "gas export", "Henry Hub", "gas terminal",
    ],
    "coal": [
        "coal", "thermal coal", "coking coal", "coal export", "coal mine",
        "coal port", "Newcastle coal", "Richards Bay coal",
    ],
    "iron_ore": [
        "iron ore", "iron ore price", "iron ore export", "iron ore mine",
        "Pilbara", "Port Hedland",
    ],
    "copper": [
        "copper", "copper mine", "copper price", "copper supply",
        "Antofagasta", "Escondida",
    ],
    "wheat": [
        "wheat", "grain", "wheat export", "grain shipment",
        "Black Sea grain", "wheat price",
    ],
    "soybeans": ["soybean", "soy", "soybean export", "soy price"],
    "aluminium": ["aluminium", "aluminum", "alumina", "bauxite"],
    "nickel": ["nickel", "nickel mine", "nickel price"],
}

# Disruption keywords for severity classification
CRITICAL_KEYWORDS = [
    "explosion", "attack", "war", "blockade", "sanctions",
    "shutdown", "collapse", "emergency", "disaster", "destroyed",
]
WARNING_KEYWORDS = [
    "strike", "flood", "storm", "hurricane", "typhoon", "earthquake",
    "disruption", "delay", "protest", "closure", "shortage",
    "drought", "fire", "accident", "spill",
]

# Region keywords
REGION_KEYWORDS: dict[str, list[str]] = {
    "Middle East": ["Iran", "Iraq", "Saudi", "Qatar", "UAE", "Hormuz", "Yemen", "Houthi"],
    "Black Sea": ["Ukraine", "Russia", "Odessa", "Novorossiysk", "Black Sea"],
    "Asia Pacific": ["China", "Japan", "Korea", "Australia", "Singapore", "Malacca"],
    "Americas": ["United States", "Brazil", "Canada", "Panama Canal", "Gulf of Mexico"],
    "Europe": ["Europe", "Rotterdam", "Mediterranean", "North Sea", "Bosphorus"],
    "Africa": ["South Africa", "Richards Bay", "Nigeria", "Suez", "Red Sea"],
}


def classify_commodity(text: str) -> str | None:
    """Match article text to a commodity based on keyword presence."""
    text_lower = text.lower()
    best_match = None
    best_count = 0
    for commodity, keywords in COMMODITY_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw.lower() in text_lower)
        if count > best_count:
            best_count = count
            best_match = commodity
    return best_match if best_count >= 1 else None


def classify_severity(text: str) -> str:
    """Classify severity based on disruption keywords."""
    text_lower = text.lower()
    for kw in CRITICAL_KEYWORDS:
        if kw in text_lower:
            return "critical"
    for kw in WARNING_KEYWORDS:
        if kw in text_lower:
            return "warning"
    return "info"


def extract_region(text: str) -> str | None:
    """Extract region from article text."""
    for region, keywords in REGION_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text.lower():
                return region
    return None


def ingest_gdelt_alerts() -> dict:
    """Poll GDELT for supply chain news events and insert into alert_events."""
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    try:
        articles = _fetch_gdelt_articles()
        logger.info("GDELT returned %d articles", len(articles))

        created = 0
        skipped = 0

        with conn.cursor() as cur:
            for article in articles:
                url = article.get("url", "")
                title = article.get("title", "")
                seendate = article.get("seendate", "")
                source_country = article.get("sourcecountry", "")
                domain = article.get("domain", "")
                language = article.get("language", "")

                if not url or not title:
                    continue

                full_text = f"{title} {domain} {source_country}"
                commodity = classify_commodity(full_text)
                if not commodity:
                    skipped += 1
                    continue

                severity = classify_severity(full_text)
                region = extract_region(full_text)

                # Dedup by source_url
                cur.execute(
                    "SELECT 1 FROM alert_events WHERE source_url = %s AND time > NOW() - INTERVAL '7 days' LIMIT 1",
                    (url,),
                )
                if cur.fetchone():
                    skipped += 1
                    continue

                event_time = datetime.now(timezone.utc)
                if seendate:
                    try:
                        event_time = datetime.strptime(
                            seendate[:15], "%Y%m%dT%H%M%S"
                        ).replace(tzinfo=timezone.utc)
                    except (ValueError, IndexError):
                        pass

                body = f"Source: {domain}"
                if language:
                    body += f" ({language})"

                metadata = {
                    "domain": domain,
                    "source_country": source_country,
                    "language": language,
                }

                cur.execute(
                    """
                    INSERT INTO alert_events (type, severity, title, body, commodity,
                        region, source, source_url, metadata, time)
                    VALUES ('news_event', %s, %s, %s, %s, %s, 'gdelt', %s, %s, %s)
                    """,
                    (
                        severity,
                        title[:500],
                        body,
                        commodity,
                        region,
                        url,
                        json.dumps(metadata),
                        event_time,
                    ),
                )
                created += 1

            conn.commit()

        if created > 0:
            _publish_alert_count(created)

        logger.info("GDELT ingest: %d created, %d skipped", created, skipped)
        return {"articles_fetched": len(articles), "alerts_created": created, "skipped": skipped}
    finally:
        conn.close()


def _fetch_gdelt_articles() -> list[dict]:
    """Fetch recent supply chain articles from GDELT GKG API."""
    query_terms = [
        "supply chain disruption",
        "port closure",
        "shipping delay",
        "oil supply",
        "commodity price",
    ]

    all_articles = []
    for term in query_terms:
        try:
            resp = requests.get(
                GDELT_GKG_URL,
                params={
                    "query": term,
                    "mode": "ArtList",
                    "maxrecords": 25,
                    "timespan": "15min",
                    "format": "json",
                    "sort": "DateDesc",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning("GDELT query '%s' returned %d", term, resp.status_code)
                continue
            data = resp.json()
            all_articles.extend(data.get("articles", []))
        except requests.RequestException as e:
            logger.warning("GDELT request failed for '%s': %s", term, e)
        except (json.JSONDecodeError, ValueError):
            logger.warning("GDELT returned invalid JSON for '%s'", term)

    # Deduplicate by URL
    seen: set[str] = set()
    unique = []
    for article in all_articles:
        url = article.get("url", "")
        if url and url not in seen:
            seen.add(url)
            unique.append(article)
    return unique


def _publish_alert_count(count: int):
    """Publish new alert notification to Redis for SSE clients."""
    try:
        import redis as sync_redis
        r = sync_redis.from_url(settings.REDIS_URL)
        r.publish("alerts", json.dumps({
            "type": "news_event",
            "count": count,
            "source": "gdelt",
            "time": datetime.now(timezone.utc).isoformat(),
        }))
        r.close()
    except Exception:
        pass
