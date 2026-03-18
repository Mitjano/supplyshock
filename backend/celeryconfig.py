"""Celery configuration — Issue #103.

Queue routing, task timeouts, and worker settings.
Import in tasks.py via: celery_app.config_from_object('celeryconfig')
"""

# ── Queue routing ──
# Three queues: ais (vessel tracking), ingestion (data fetching), analytics (reports/sims)
task_routes = {
    # AIS / vessel tasks
    "refresh_latest_vessel_positions": {"queue": "ais"},
    "stream_ais_positions": {"queue": "ais"},
    # Ingestion tasks
    "ingest_eia_prices": {"queue": "ingestion"},
    "ingest_eia_inventories": {"queue": "ingestion"},
    "import_eia_steo": {"queue": "ingestion"},
    "ingest_comtrade": {"queue": "ingestion"},
    "ingest_port_congestion": {"queue": "ingestion"},
    "ingest_weather_alerts": {"queue": "ingestion"},
    "ingest_crop_reports": {"queue": "ingestion"},
    "ingest_fx_rates": {"queue": "ingestion"},
    # Analytics / simulation tasks
    "run_simulation": {"queue": "analytics"},
    "generate_report": {"queue": "analytics"},
    "compute_risk_scores": {"queue": "analytics"},
    "celery_health_check": {"queue": "ingestion"},
    "check_data_freshness_task": {"queue": "ingestion"},
}

# Default queue for tasks not explicitly routed
task_default_queue = "ingestion"

# ── Task timeouts ──
# Per-task soft/hard time limits (seconds)
task_time_limit = 600  # 10 min hard limit (default)
task_soft_time_limit = 540  # 9 min soft limit (default)

task_annotations = {
    # Ingestion tasks: 5 min
    "ingest_eia_prices": {"time_limit": 300, "soft_time_limit": 270},
    "ingest_eia_inventories": {"time_limit": 300, "soft_time_limit": 270},
    "import_eia_steo": {"time_limit": 300, "soft_time_limit": 270},
    "ingest_comtrade": {"time_limit": 300, "soft_time_limit": 270},
    "ingest_port_congestion": {"time_limit": 300, "soft_time_limit": 270},
    "ingest_fx_rates": {"time_limit": 300, "soft_time_limit": 270},
    # Analytics tasks: 10 min
    "run_simulation": {"time_limit": 600, "soft_time_limit": 540},
    "generate_report": {"time_limit": 600, "soft_time_limit": 540},
    "compute_risk_scores": {"time_limit": 600, "soft_time_limit": 540},
    # AIS: 5 min
    "refresh_latest_vessel_positions": {"time_limit": 300, "soft_time_limit": 270},
}

# ── Serialization ──
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

# ── Timezone ──
timezone = "UTC"
enable_utc = True

# ── Reliability ──
task_acks_late = True
worker_prefetch_multiplier = 1
task_reject_on_worker_lost = True
