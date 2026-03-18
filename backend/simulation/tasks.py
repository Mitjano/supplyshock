import asyncio
import logging

from celery import Celery
from celery.schedules import crontab
from config import settings

logger = logging.getLogger("supplyshock.tasks")

celery_app = Celery(
    "supplyshock",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_time_limit=600,
    beat_schedule={
        "refresh-vessel-positions": {
            "task": "refresh_latest_vessel_positions",
            "schedule": 300.0,  # every 5 minutes (not 30s — too aggressive)
        },
        "ingest-eia-prices": {
            "task": "ingest_eia_prices",
            "schedule": crontab(minute=0, hour="*/6"),  # every 6 hours
        },
        "ingest-nasdaq-prices": {
            "task": "ingest_nasdaq_prices",
            "schedule": crontab(minute=15, hour="*"),  # every hour at :15
        },
        "ingest-gdelt-alerts": {
            "task": "ingest_gdelt_alerts",
            "schedule": crontab(minute="*/15"),  # every 15 minutes
        },
        "detect-ais-anomalies": {
            "task": "detect_ais_anomalies",
            "schedule": crontab(minute="*/30"),  # every 30 minutes
        },
        "start-ais-stream": {
            "task": "start_ais_stream",
            "schedule": 60.0,  # check every 60s; task uses a flag to prevent duplicates
        },
        "db-maintenance": {
            "task": "db_maintenance",
            "schedule": crontab(minute=0, hour=3),  # daily at 3:00 UTC
        },
        "celery-health-check": {
            "task": "celery_health_check",
            "schedule": crontab(minute="*/5"),  # every 5 minutes
        },
        "detect-voyages": {
            "task": "detect_voyages",
            "schedule": 300.0,  # every 5 minutes
        },
        "detect-floating-storage": {
            "task": "detect_floating_storage",
            "schedule": 3600.0,  # every 1 hour
        },
    },
)


# ── Materialized view refresh ──

@celery_app.task(name="refresh_latest_vessel_positions", bind=True, max_retries=3, default_retry_delay=60)
def refresh_latest_vessel_positions(self):
    """Refresh the latest_vessel_positions materialized view (every 5 min)."""
    import psycopg2
    try:
        conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY latest_vessel_positions")
        finally:
            conn.close()
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Price ingestion ──

@celery_app.task(name="ingest_eia_prices", bind=True, max_retries=3, default_retry_delay=60)
def ingest_eia_prices_task(self):
    """Fetch EIA energy prices (crude oil, LNG)."""
    try:
        from ingestion.eia import ingest_eia_prices
        return ingest_eia_prices()
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(name="ingest_nasdaq_prices", bind=True, max_retries=3, default_retry_delay=60)
def ingest_nasdaq_prices_task(self):
    """Fetch commodity prices (metals, agriculture)."""
    try:
        from ingestion.prices import ingest_nasdaq_prices
        return ingest_nasdaq_prices()
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Alert ingestion ──

@celery_app.task(name="ingest_gdelt_alerts", bind=True, max_retries=3, default_retry_delay=60)
def ingest_gdelt_alerts_task(self):
    """Poll GDELT for supply chain news events."""
    try:
        from ingestion.gdelt import ingest_gdelt_alerts
        return ingest_gdelt_alerts()
    except Exception as exc:
        raise self.retry(exc=exc)


# ── Simulation engine (#27) ──

@celery_app.task(name="run_simulation", bind=True, time_limit=600, max_retries=1)
def run_simulation(self, simulation_id: str):
    """Run a supply chain disruption simulation.

    Orchestrates the OASIS-based multi-agent simulation:
    1. Load simulation config from DB
    2. Initialize commodity agents + environment
    3. Run simulation rounds, publishing progress to Redis
    4. Write results to DB and mark as completed
    """
    import json
    import logging
    import psycopg2
    import redis as sync_redis
    from datetime import datetime, timezone

    logger = logging.getLogger("simulation")

    try:
        conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    except Exception as exc:
        raise self.retry(exc=exc)

    try:
        with conn.cursor() as cur:
            # Load simulation config
            cur.execute("""
                SELECT id, node, event_type, parameters, agents_count
                FROM simulations WHERE id = %s
            """, (simulation_id,))
            sim = cur.fetchone()
            if not sim:
                logger.error("Simulation %s not found", simulation_id)
                return {"error": "not_found"}

            sim_id, node, event_type, parameters, agents_count = sim
            if isinstance(parameters, str):
                parameters = json.loads(parameters)

            # Mark as running
            cur.execute("""
                UPDATE simulations SET status = 'running', started_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (simulation_id,))
            conn.commit()

            # Publish progress to Redis for SSE
            r = None
            try:
                r = sync_redis.from_url(settings.REDIS_URL)
            except Exception:
                pass

            def publish_progress(progress: int, log_line: str):
                cur.execute("""
                    UPDATE simulations
                    SET progress = %s, progress_log = array_append(progress_log, %s), updated_at = NOW()
                    WHERE id = %s
                """, (progress, log_line, simulation_id))
                conn.commit()
                if r:
                    try:
                        r.publish(f"sim:{simulation_id}", json.dumps({
                            "progress": progress,
                            "log": log_line,
                            "time": datetime.now(timezone.utc).isoformat(),
                        }))
                    except Exception:
                        pass

            # ── Simulation engine ──
            # Dual mode: deterministic (fast, free) or multi-agent OASIS (LLM-powered)

            publish_progress(5, f"Initializing simulation: {event_type} at {node}")

            # Fetch historical prices for affected commodities
            cur.execute("""
                SELECT commodities FROM bottleneck_nodes WHERE slug = %s
            """, (node,))
            node_row = cur.fetchone()
            affected_commodities = node_row[0] if node_row else ["crude_oil"]

            publish_progress(10, f"Affected commodities: {', '.join(affected_commodities)}")

            # Fetch baseline prices
            baseline_prices = {}
            for commodity in affected_commodities:
                cur.execute("""
                    SELECT benchmark, price FROM commodity_prices
                    WHERE commodity = %s
                    ORDER BY time DESC LIMIT 1
                """, (commodity,))
                price_row = cur.fetchone()
                if price_row:
                    baseline_prices[commodity] = {"benchmark": price_row[0], "price": float(price_row[1])}

            publish_progress(20, f"Baseline prices loaded for {len(baseline_prices)} commodities")

            # Fetch node risk profile
            cur.execute("""
                SELECT name, global_share_pct, baseline_risk, annual_volume_mt
                FROM bottleneck_nodes WHERE slug = %s
            """, (node,))
            node_info = cur.fetchone()

            duration_weeks = parameters.get("duration_weeks", 4)
            intensity = parameters.get("intensity", 0.7)
            horizon_days = parameters.get("horizon_days", 90)
            sim_mode = parameters.get("mode", "deterministic")

            # ── MULTI-AGENT MODE (OASIS) ──
            if sim_mode == "multi_agent" and settings.CLAUDE_API_KEY:
                publish_progress(25, "Starting multi-agent OASIS simulation")

                from simulation.engine import SimulationEngine

                sim_config = {
                    "simulation_id": simulation_id,
                    "node": node,
                    "node_name": node_info[0] if node_info else node,
                    "event_type": event_type,
                    "duration_weeks": duration_weeks,
                    "intensity": intensity,
                    "horizon_days": horizon_days,
                    "agents_count": agents_count or parameters.get("agents", 50),
                    "affected_commodities": affected_commodities,
                    "global_share_pct": float(node_info[1]) if node_info else 10.0,
                }

                engine = SimulationEngine(
                    sim_config=sim_config,
                    baseline_prices=baseline_prices,
                    node_info=node_info,
                    db_url_sync=settings.DATABASE_URL_SYNC,
                    claude_api_key=settings.CLAUDE_API_KEY,
                    publish_progress=publish_progress,
                )

                # Run async engine in sync Celery worker
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(engine.run())
                finally:
                    loop.close()

            # ── DETERMINISTIC MODE (default) ──
            else:
                publish_progress(30, f"Running deterministic model over {horizon_days}-day horizon")

                import math
                import random
                random.seed(hash(f"{simulation_id}{node}{event_type}"))

                event_multipliers = {
                    "flood": 1.2, "strike": 0.8, "blockade": 1.5,
                    "storm": 1.0, "earthquake": 1.8, "war": 2.0,
                    "sanctions": 1.3, "drought": 0.9, "pandemic": 0.7,
                }
                event_mult = event_multipliers.get(event_type, 1.0)

                global_share = float(node_info[1]) / 100 if node_info else 0.1
                base_risk = node_info[2] if node_info else 5

                predictions = {}
                for commodity, bp in baseline_prices.items():
                    weekly_prices = []
                    price = bp["price"]
                    peak_week = min(duration_weeks, max(1, int(duration_weeks * 0.6)))

                    for week in range(1, horizon_days // 7 + 1):
                        if week <= duration_weeks:
                            disruption_factor = intensity * global_share * event_mult
                            progress_ratio = min(week / peak_week, 1.0)
                            shock = price * disruption_factor * progress_ratio
                            noise = random.gauss(0, price * 0.02)
                            week_price = price + shock + noise
                        else:
                            recovery_week = week - duration_weeks
                            recovery_rate = 0.15
                            remaining_shock = (weekly_prices[-1] - price) * math.exp(-recovery_rate * recovery_week)
                            noise = random.gauss(0, price * 0.015)
                            week_price = price + remaining_shock + noise

                        weekly_prices.append(round(week_price, 2))

                    peak_price = max(weekly_prices)
                    peak_change_pct = round((peak_price - price) / price * 100, 1)

                    predictions[commodity] = {
                        "benchmark": bp["benchmark"],
                        "baseline_price": price,
                        "weekly_prices": weekly_prices,
                        "peak_price": peak_price,
                        "peak_change_pct": peak_change_pct,
                        "recovery_week": duration_weeks + int(math.log(0.05) / (-0.15)) if peak_change_pct > 0 else 0,
                    }

                    progress_pct = 30 + int(60 * (list(baseline_prices.keys()).index(commodity) + 1) / len(baseline_prices))
                    publish_progress(min(progress_pct, 90), f"Predicted {commodity}: +{peak_change_pct}% peak impact")

                result = {
                    "node": node,
                    "node_name": node_info[0] if node_info else node,
                    "event_type": event_type,
                    "duration_weeks": duration_weeks,
                    "intensity": intensity,
                    "horizon_days": horizon_days,
                    "global_share_pct": float(global_share * 100),
                    "predictions": predictions,
                    "risk_score": round(min(10, base_risk * intensity * event_mult), 1),
                    "simulation_type": "deterministic",
                    "summary": f"{'High' if intensity > 0.7 else 'Moderate'} disruption at {node_info[0] if node_info else node}. "
                               f"Peak commodity price impact: {max((p['peak_change_pct'] for p in predictions.values()), default=0):.1f}%.",
                }

            publish_progress(95, "Finalizing results")

            # Write results
            cur.execute("""
                UPDATE simulations
                SET status = 'completed', result = %s, progress = 100,
                    completed_at = NOW(), updated_at = NOW()
                WHERE id = %s
            """, (json.dumps(result), simulation_id))
            conn.commit()

            publish_progress(100, "Simulation completed")

            # Publish completion event
            if r:
                try:
                    r.publish(f"sim:{simulation_id}", json.dumps({
                        "status": "completed", "progress": 100,
                        "time": datetime.now(timezone.utc).isoformat(),
                    }))
                    r.close()
                except Exception:
                    pass

            return {"status": "completed", "simulation_id": simulation_id}

    except Exception as exc:
        logger.exception("Simulation %s failed", simulation_id)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE simulations
                    SET status = 'failed', error_message = %s, updated_at = NOW()
                    WHERE id = %s
                """, (str(exc)[:500], simulation_id))
                conn.commit()
        except Exception:
            pass
        raise
    finally:
        conn.close()


# ── Report generation (#29) ──

@celery_app.task(name="generate_report", bind=True, time_limit=120, max_retries=2, default_retry_delay=30)
def generate_report(self, report_id: str):
    """Generate a PDF report using Claude API for analysis + WeasyPrint for rendering.

    1. Fetch simulation results (if linked)
    2. Fetch relevant commodity price data
    3. Call Claude API for narrative analysis
    4. Render HTML template to PDF via WeasyPrint
    5. Update report record with PDF URL and metadata
    """
    import json
    import logging
    import psycopg2

    logger = logging.getLogger("report_gen")

    try:
        conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    except Exception as exc:
        raise self.retry(exc=exc)

    try:
        with conn.cursor() as cur:
            # Load report
            cur.execute("""
                SELECT r.id, r.title, r.simulation_id, r.user_id
                FROM reports r WHERE r.id = %s
            """, (report_id,))
            report = cur.fetchone()
            if not report:
                logger.error("Report %s not found", report_id)
                return {"error": "not_found"}

            _, title, simulation_id, user_id = report

            # Load simulation results if linked
            sim_result = None
            if simulation_id:
                cur.execute("SELECT result, title, node, event_type FROM simulations WHERE id = %s", (simulation_id,))
                sim_row = cur.fetchone()
                if sim_row and sim_row[0]:
                    sim_result = sim_row[0] if isinstance(sim_row[0], dict) else json.loads(sim_row[0])
                    sim_result["sim_title"] = sim_row[1]
                    sim_result["sim_node"] = sim_row[2]
                    sim_result["sim_event"] = sim_row[3]

            # Fetch latest commodity prices for context
            cur.execute("""
                SELECT commodity, benchmark, price, currency, unit, time
                FROM commodity_prices
                WHERE time > NOW() - INTERVAL '7 days'
                ORDER BY commodity, time DESC
            """)
            recent_prices = {}
            for row in cur.fetchall():
                key = row[0]
                if key not in recent_prices:
                    recent_prices[key] = {
                        "benchmark": row[1], "price": float(row[2]),
                        "currency": row[3], "unit": row[4],
                    }

            # Generate analysis via Claude API
            analysis_text = ""
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)

                context_parts = [f"Report title: {title}"]
                if sim_result:
                    context_parts.append(f"Simulation: {sim_result.get('sim_title', 'N/A')}")
                    context_parts.append(f"Event: {sim_result.get('event_type', 'N/A')} at {sim_result.get('node_name', 'N/A')}")
                    context_parts.append(f"Summary: {sim_result.get('summary', 'N/A')}")
                    for commodity, pred in sim_result.get("predictions", {}).items():
                        context_parts.append(
                            f"  {commodity}: baseline ${pred['baseline_price']}, "
                            f"peak +{pred['peak_change_pct']}%, "
                            f"recovery ~week {pred.get('recovery_week', 'N/A')}"
                        )
                if recent_prices:
                    context_parts.append("\nCurrent market prices:")
                    for c, p in list(recent_prices.items())[:15]:
                        context_parts.append(f"  {c}: ${p['price']} {p['currency']}/{p['unit']}")

                prompt = "\n".join(context_parts)

                message = client.messages.create(
                    model="claude-sonnet-4-6-20250514",
                    max_tokens=2000,
                    messages=[{
                        "role": "user",
                        "content": f"""You are a commodity market analyst at a supply chain intelligence firm.
Write a professional market analysis report based on the following data.
Structure: Executive Summary, Market Impact Analysis, Price Predictions, Risk Assessment, Recommendations.
Use clear, concise language suitable for commodity traders and supply chain managers.
Output in HTML format (use <h2>, <p>, <ul>, <table> tags).

Data:
{prompt}""",
                    }],
                )
                analysis_text = message.content[0].text
            except Exception as e:
                logger.warning("Claude API failed for report %s: %s", report_id, e)
                # Fallback: generate basic HTML from data
                analysis_text = f"<h2>Market Analysis Report</h2><p>Report: {title}</p>"
                if sim_result:
                    analysis_text += f"<p>{sim_result.get('summary', '')}</p>"

            # Build full HTML document
            html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
    body {{ font-family: 'Inter', 'Helvetica Neue', sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #1a1a2e; line-height: 1.6; }}
    h1 {{ color: #0f3460; border-bottom: 3px solid #16c79a; padding-bottom: 8px; }}
    h2 {{ color: #0f3460; margin-top: 2em; }}
    table {{ width: 100%; border-collapse: collapse; margin: 1em 0; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    th {{ background: #0f3460; color: white; }}
    tr:nth-child(even) {{ background: #f8f9fa; }}
    .header {{ text-align: center; margin-bottom: 2em; }}
    .footer {{ margin-top: 3em; padding-top: 1em; border-top: 1px solid #ddd; font-size: 0.85em; color: #666; text-align: center; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; font-weight: 600; }}
    .badge-high {{ background: #fee2e2; color: #dc2626; }}
    .badge-moderate {{ background: #fef3c7; color: #d97706; }}
    .badge-low {{ background: #d1fae5; color: #059669; }}
</style>
</head>
<body>
<div class="header">
    <h1>{title}</h1>
    <p style="color:#666;">SupplyShock Intelligence Report</p>
</div>
{analysis_text}
<div class="footer">
    <p>Generated by SupplyShock &mdash; supplyshock.pl</p>
</div>
</body>
</html>"""

            # Generate PDF via WeasyPrint
            pdf_bytes = None
            page_count = 1
            try:
                from weasyprint import HTML
                pdf_doc = HTML(string=html_content).render()
                pdf_bytes = pdf_doc.write_pdf()
                page_count = len(pdf_doc.pages)
            except ImportError:
                logger.warning("WeasyPrint not installed, storing HTML only")
                pdf_bytes = html_content.encode("utf-8")
            except Exception as e:
                logger.warning("PDF generation failed: %s", e)
                pdf_bytes = html_content.encode("utf-8")

            file_size = len(pdf_bytes)

            # Store PDF (local for now, S3/CDN in production)
            import os
            pdf_dir = os.path.join(os.path.dirname(__file__), "..", "data", "reports")
            os.makedirs(pdf_dir, exist_ok=True)
            pdf_path = os.path.join(pdf_dir, f"{report_id}.pdf")
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)

            pdf_url = f"/data/reports/{report_id}.pdf"

            # Update report record
            cur.execute("""
                UPDATE reports
                SET status = 'ready', pdf_url = %s, page_count = %s,
                    file_size_bytes = %s, updated_at = NOW()
                WHERE id = %s
            """, (pdf_url, page_count, file_size, report_id))
            conn.commit()

            logger.info("Report %s generated: %d pages, %d bytes", report_id, page_count, file_size)
            return {"status": "ready", "report_id": report_id, "page_count": page_count}

    except Exception as exc:
        logger.exception("Report generation failed for %s", report_id)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE reports SET status = 'failed', updated_at = NOW() WHERE id = %s
                """, (report_id,))
                conn.commit()
        except Exception:
            pass
        raise self.retry(exc=exc)
    finally:
        conn.close()


# ── AIS anomaly detection (Issue #19) ──

@celery_app.task(name="detect_ais_anomalies", bind=True, max_retries=3, default_retry_delay=60)
def detect_ais_anomalies(self):
    """Check vessel congestion at bottleneck nodes.

    For each bottleneck_node, count vessels within 50km radius.
    If count > mean + 2*std (30-day rolling), generate AIS_ANOMALY alert.

    congestion_index: 0-10 scale
    risk_level vocabulary: 'normal', 'elevated', 'high', 'critical'
    """
    import json
    import psycopg2
    import redis as sync_redis
    from datetime import datetime, timezone

    try:
        conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    except Exception as exc:
        raise self.retry(exc=exc)

    try:
        with conn.cursor() as cur:
            # Get bottleneck nodes with coordinates
            cur.execute("""
                SELECT id, slug, name, latitude, longitude, baseline_risk
                FROM bottleneck_nodes
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            """)
            nodes = cur.fetchall()

            for node_id, slug, name, lat, lon, baseline_risk in nodes:
                # Count vessels within ~50km (0.45 degrees approx)
                cur.execute("""
                    SELECT COUNT(DISTINCT mmsi) as cnt,
                           AVG(speed_knots) as avg_speed
                    FROM vessel_positions
                    WHERE time > NOW() - INTERVAL '1 hour'
                      AND latitude BETWEEN %s AND %s
                      AND longitude BETWEEN %s AND %s
                """, (lat - 0.45, lat + 0.45, lon - 0.45, lon + 0.45))

                result = cur.fetchone()
                vessel_count = result[0] or 0
                avg_speed = result[1]

                # Calculate congestion index on 0-10 scale
                congestion = min(vessel_count / 5.0, 10.0)

                # Risk level vocabulary: normal, elevated, high, critical
                if congestion >= 8:
                    risk_level = "critical"
                elif congestion >= 5:
                    risk_level = "high"
                elif congestion >= 3:
                    risk_level = "elevated"
                else:
                    risk_level = "normal"

                # Insert status record
                cur.execute("""
                    INSERT INTO chokepoint_status (node_id, vessel_count, avg_speed_knots,
                        congestion_index, risk_level, time)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (node_id, vessel_count, avg_speed, congestion, risk_level))

                # Check for anomaly: get 30-day stats
                cur.execute("""
                    SELECT AVG(vessel_count), STDDEV(vessel_count)
                    FROM chokepoint_status
                    WHERE node_id = %s AND time > NOW() - INTERVAL '30 days'
                """, (node_id,))
                stats = cur.fetchone()
                mean_count = stats[0] or 0
                std_count = stats[1] or 0

                # Anomaly if > mean + 2*std and at least 10 vessels
                threshold = mean_count + 2 * std_count
                if vessel_count > threshold and vessel_count >= 10 and std_count > 0:
                    cur.execute("""
                        INSERT INTO alert_events (type, severity, title, body,
                            source, metadata, time)
                        VALUES ('ais_anomaly', 'high',
                            %s, %s, %s, %s, NOW())
                    """, (
                        f"Unusual vessel congestion at {name}",
                        f"{vessel_count} vessels detected (normal: {mean_count:.0f}\u00b1{std_count:.0f})",
                        "ais_anomaly",
                        json.dumps({"node_slug": slug, "vessel_count": vessel_count,
                                    "threshold": threshold, "congestion_index": congestion}),
                    ))

                    # Publish alert via Redis
                    try:
                        r = sync_redis.from_url(settings.REDIS_URL)
                        r.publish("alerts", json.dumps({
                            "type": "ais_anomaly",
                            "severity": "high",
                            "title": f"Unusual vessel congestion at {name}",
                            "node_slug": slug,
                            "vessel_count": vessel_count,
                            "time": datetime.now(timezone.utc).isoformat(),
                        }))
                        r.close()
                    except Exception:
                        pass

        conn.commit()
    finally:
        conn.close()


# ── AIS WebSocket consumer ──

# Flag to prevent duplicate AIS stream consumers
_ais_stream_running = False

@celery_app.task(name="start_ais_stream", bind=True, max_retries=3, default_retry_delay=60)
def start_ais_stream(self):
    """Start the AIS WebSocket consumer as a long-running Celery task.

    Uses a module-level flag to prevent duplicate consumers when beat
    triggers this task repeatedly.
    """
    global _ais_stream_running
    if _ais_stream_running:
        return "AIS stream already running"

    _ais_stream_running = True
    from ingestion.ais_stream import run_ais_consumer

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_ais_consumer())
    except Exception as exc:
        _ais_stream_running = False
        raise self.retry(exc=exc, countdown=30)
    finally:
        _ais_stream_running = False
        loop.close()


# ── Database maintenance (#104) ──

@celery_app.task(name="db_maintenance", bind=True, max_retries=2, default_retry_delay=120)
def db_maintenance(self):
    """Daily database maintenance:
    - Clean expired report share tokens
    - Clean stale simulations stuck in 'queued'/'running' > 24h
    - Vacuum analyze key tables
    - Log TimescaleDB compression/retention job stats
    """
    import logging
    import psycopg2

    logger = logging.getLogger("db_maintenance")

    try:
        conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
        conn.autocommit = True
    except Exception as exc:
        raise self.retry(exc=exc)

    try:
        with conn.cursor() as cur:
            # 1. Expire share tokens past their expiry
            cur.execute("""
                UPDATE reports
                SET share_token = NULL, share_expires_at = NULL, updated_at = NOW()
                WHERE share_expires_at < NOW() AND share_token IS NOT NULL
            """)
            expired_shares = cur.rowcount
            logger.info("Cleaned %d expired report share tokens", expired_shares)

            # 2. Mark stuck simulations as 'failed'
            cur.execute("""
                UPDATE simulations
                SET status = 'failed', error_message = 'Timed out — stuck for >24h', updated_at = NOW()
                WHERE status IN ('queued', 'running')
                  AND created_at < NOW() - INTERVAL '24 hours'
            """)
            stuck_sims = cur.rowcount
            logger.info("Marked %d stuck simulations as failed", stuck_sims)

            # 3. Log TimescaleDB job stats
            cur.execute("""
                SELECT j.hypertable_name, j.proc_name,
                       js.last_run_status, js.last_successful_finish,
                       js.total_successes, js.total_failures
                FROM timescaledb_information.jobs j
                LEFT JOIN timescaledb_information.job_stats js
                    ON j.job_id = js.job_id
                ORDER BY j.hypertable_name
            """)
            jobs = cur.fetchall()
            for ht, proc, status, last_ok, successes, failures in jobs:
                logger.info(
                    "TimescaleDB job: %s.%s — status=%s, last_ok=%s, ok=%s, fail=%s",
                    ht, proc, status, last_ok, successes, failures,
                )

            # 4. Log hypertable sizes
            cur.execute("""
                SELECT hypertable_name,
                       pg_size_pretty(hypertable_size(format('%I.%I', hypertable_schema, hypertable_name)::regclass)) as size,
                       num_chunks, num_compressed_chunks
                FROM timescaledb_information.hypertables
            """)
            for ht_name, size, chunks, compressed in cur.fetchall():
                logger.info(
                    "Hypertable %s: size=%s, chunks=%s (compressed=%s)",
                    ht_name, size, chunks, compressed,
                )

        return {
            "expired_shares": expired_shares,
            "stuck_simulations": stuck_sims,
            "timescaledb_jobs": len(jobs),
        }
    finally:
        conn.close()


# ── Celery health check (#103) ──

@celery_app.task(name="celery_health_check", bind=True, max_retries=0)
def celery_health_check(self):
    """Periodic health check — publishes worker stats to Redis for monitoring.

    Logs active/reserved task counts per worker and stores a heartbeat timestamp.
    """
    import json
    import logging
    import redis as sync_redis
    from datetime import datetime, timezone

    logger = logging.getLogger("celery_health")

    try:
        # Inspect active workers
        inspector = celery_app.control.inspect()
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}
        stats = inspector.stats() or {}

        worker_status = {}
        for worker_name in set(list(active.keys()) + list(reserved.keys()) + list(stats.keys())):
            worker_status[worker_name] = {
                "active_tasks": len(active.get(worker_name, [])),
                "reserved_tasks": len(reserved.get(worker_name, [])),
                "uptime": stats.get(worker_name, {}).get("clock", None),
                "pool_size": stats.get(worker_name, {}).get("pool", {}).get("max-concurrency", None),
            }

        logger.info("Celery workers: %d online", len(worker_status))
        for name, info in worker_status.items():
            logger.info(
                "  %s: active=%d, reserved=%d, pool=%s",
                name, info["active_tasks"], info["reserved_tasks"], info["pool_size"],
            )

        # Store heartbeat in Redis
        try:
            r = sync_redis.from_url(settings.REDIS_URL)
            r.setex(
                "celery:health",
                300,  # 5 min TTL
                json.dumps({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "workers": worker_status,
                    "worker_count": len(worker_status),
                }),
            )
            r.close()
        except Exception:
            pass

        return {"workers": len(worker_status), "status": "healthy" if worker_status else "no_workers"}

    except Exception as e:
        logger.error("Celery health check failed: %s", e)
        return {"status": "error", "error": str(e)}


# ── Voyage detection ──

@celery_app.task(name="detect_voyages", bind=True, max_retries=2, default_retry_delay=30)
def detect_voyages_task(self):
    """Detect port enter/exit events and create/close voyages (every 5 min)."""
    try:
        from ingestion.voyage_detector import detect_voyages
        detect_voyages()
    except Exception as exc:
        logger.error("Voyage detection failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(name="detect_floating_storage", bind=True, max_retries=2, default_retry_delay=60)
def detect_floating_storage_task(self):
    """Detect laden vessels stationary >7 days outside ports (every 1h)."""
    try:
        from ingestion.voyage_detector import detect_floating_storage
        detect_floating_storage()
    except Exception as exc:
        logger.error("Floating storage detection failed: %s", exc)
        raise self.retry(exc=exc)
