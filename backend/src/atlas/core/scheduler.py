"""APScheduler module for Atlas background jobs.

Manages an AsyncIOScheduler with a single job:
  framework19_poll — calls evaluate_framework19 every 2 minutes during
  market hours (09:30-16:00 ET, weekdays only).

The scheduler is wired into FastAPI via the lifespan context manager in
atlas.main.  It is started on app startup and shut down gracefully on exit.

V1 constraint: database session only — no Redis, no Celery.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Eastern Time timezone for market hours check.
_ET_TZ = pytz.timezone("America/New_York")

# Market session boundaries (hardcoded here only — actual evaluation uses
# atlas_config.  These constants guard the scheduler from running at all
# outside of a generous pre/post-market window to avoid DB load overnight).
_SESSION_START_HOUR: int = 9
_SESSION_START_MINUTE: int = 25  # 5-minute pre-open buffer
_SESSION_END_HOUR: int = 16
_SESSION_END_MINUTE: int = 5    # 5-minute post-close buffer

# Scheduler instance (module-level singleton).
_scheduler: AsyncIOScheduler | None = None


def _is_within_market_window() -> bool:
    """Return True when current ET time is within the market evaluation window.

    Uses a slightly broader window than F19's strict 09:30-16:00 to ensure
    the scheduler runs at open and close.  Weekends always return False.
    """
    now_et = datetime.now(_ET_TZ)
    if now_et.weekday() >= 5:
        return False
    open_time = now_et.replace(
        hour=_SESSION_START_HOUR,
        minute=_SESSION_START_MINUTE,
        second=0,
        microsecond=0,
    )
    close_time = now_et.replace(
        hour=_SESSION_END_HOUR,
        minute=_SESSION_END_MINUTE,
        second=0,
        microsecond=0,
    )
    return open_time <= now_et <= close_time


async def _run_framework19_poll() -> None:
    """Job body: evaluate F19 if within market window.

    Creates its own DB session for the duration of the job.
    Logs the result and exits.  Errors are caught so the scheduler
    does not stop running if one evaluation fails.
    """
    if not _is_within_market_window():
        logger.debug("F19 scheduler: outside market window, skipping evaluation")
        return

    logger.info(
        "F19 scheduler: running evaluation",
        extra={"utc_time": datetime.now(UTC).isoformat()},
    )

    try:
        # Import here to avoid circular imports and to delay DB engine
        # initialisation until after the app has fully started.
        from atlas.db.session import get_async_session_factory
        from atlas.services.framework19_service import evaluate_framework19

        async_session_factory = get_async_session_factory()
        async with async_session_factory() as session:
            result = await evaluate_framework19(session)

        logger.info(
            "F19 scheduler: evaluation complete",
            extra={
                "status": result.f19_status,
                "f19_active": result.f19_active,
                "drop_pct": result.nvda_drop.drop_pct,
            },
        )
    except Exception as exc:
        logger.error(
            "F19 scheduler: evaluation failed",
            extra={"error": repr(exc)},
        )


async def start_scheduler() -> None:
    """Start the APScheduler AsyncIOScheduler.

    Called from the FastAPI lifespan context manager on startup.
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        logger.warning("Scheduler already running — skipping start")
        return

    # 2-minute interval: spec says poll every 2 minutes during market hours.
    poll_interval_seconds: int = 120  # 2 minutes

    _scheduler = AsyncIOScheduler(timezone="America/New_York")
    _scheduler.add_job(
        _run_framework19_poll,
        trigger="interval",
        seconds=poll_interval_seconds,
        id="framework19_poll",
        name="Framework 19 NVDA Kill Switch Poll",
        replace_existing=True,
        misfire_grace_time=60,
    )
    _scheduler.start()
    logger.info(
        "Atlas scheduler started",
        extra={"interval_seconds": poll_interval_seconds},
    )


async def stop_scheduler() -> None:
    """Stop the APScheduler instance gracefully.

    Called from the FastAPI lifespan context manager on shutdown.
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Atlas scheduler stopped")
    _scheduler = None
