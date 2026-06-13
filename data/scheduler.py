"""
MetaMind — APScheduler background scheduler for automated ETL.

Runs the full ETL pipeline on a cron schedule (default: 3 AM UTC daily).
Uses a thread-safe singleton pattern to prevent duplicate schedulers.

Usage::

    from data.scheduler import start_scheduler, stop_scheduler

    start_scheduler()   # non-blocking — runs in background thread
    stop_scheduler()    # graceful shutdown
"""

import logging
import threading
from pathlib import Path
from typing import Any

import yaml
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton state
# ---------------------------------------------------------------------------

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()

_JOB_ID = "metamind_daily_etl"


# ---------------------------------------------------------------------------
# Config helper
# ---------------------------------------------------------------------------

def _load_config() -> dict[str, Any]:
    """Load config.yaml from the project root."""
    config_path = Path(__file__).resolve().parent.parent / "config.yaml"
    with open(config_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# ETL job function
# ---------------------------------------------------------------------------

def _run_etl_job() -> None:
    """Execute the full ETL pipeline as a scheduled job.

    This function is invoked by APScheduler on each trigger.
    Errors are caught and logged so the scheduler keeps running.
    """
    logger.info("Scheduled ETL job starting …")
    try:
        # Late imports to avoid circular dependencies and ensure
        # the latest code is used on each invocation.
        from data.etl import run_etl
        from data.db_loader import load_all
        from db.connection import get_engine

        etl_data = run_etl(full=True)
        engine = get_engine()
        counts = load_all(engine=engine, etl_data=etl_data)

        logger.info("Scheduled ETL job completed successfully")
        for table, count in counts.items():
            logger.info("  %-25s %8d operations", table, count)

    except Exception:
        logger.exception("Scheduled ETL job failed")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_scheduler() -> BackgroundScheduler:
    """Start the background ETL scheduler (singleton).

    If the scheduler is already running, this is a no-op and returns
    the existing instance.

    Returns:
        The running ``BackgroundScheduler`` instance.
    """
    global _scheduler

    with _lock:
        if _scheduler is not None and _scheduler.running:
            logger.info("Scheduler already running — skipping start")
            return _scheduler

        config = _load_config()
        schedule_cfg = config.get("schedule", {})
        hour: int = schedule_cfg.get("daily_etl_hour", 3)
        minute: int = schedule_cfg.get("daily_etl_minute", 0)

        # Configure logging to file
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / "etl.log", encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
            ),
        )
        logging.getLogger("data").addHandler(file_handler)
        logging.getLogger("db").addHandler(file_handler)
        logger.addHandler(file_handler)

        _scheduler = BackgroundScheduler(
            daemon=True,
            job_defaults={
                "coalesce": True,       # merge missed runs
                "max_instances": 1,     # never run concurrently
            },
        )

        trigger = CronTrigger(hour=hour, minute=minute, timezone="UTC")
        _scheduler.add_job(
            _run_etl_job,
            trigger=trigger,
            id=_JOB_ID,
            name="MetaMind Daily ETL",
            replace_existing=True,
        )

        _scheduler.start()
        logger.info(
            "Scheduler started — ETL job scheduled at %02d:%02d UTC daily",
            hour, minute,
        )

        return _scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the background scheduler.

    Safe to call even if the scheduler is not running.
    """
    global _scheduler

    with _lock:
        if _scheduler is None or not _scheduler.running:
            logger.info("Scheduler is not running — nothing to stop")
            return

        _scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped gracefully")
        _scheduler = None
