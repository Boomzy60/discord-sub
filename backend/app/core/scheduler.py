"""Wires the periodic subscription-expiration sweep into APScheduler."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.jobs.expire_subscriptions import expire_due_subscriptions

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

EXPIRE_SUBSCRIPTIONS_JOB_ID = "expire_subscriptions"


async def _run_expire_subscriptions_job() -> None:
    async with AsyncSessionLocal() as db:
        expired_count = await expire_due_subscriptions(db)
        if expired_count:
            logger.info("Expired %d subscription(s)", expired_count)


def start_scheduler() -> None:
    """Register and start the periodic expiration job. Safe to call once at app startup."""
    settings = get_settings()
    scheduler.add_job(
        _run_expire_subscriptions_job,
        "interval",
        minutes=settings.expiration_check_interval_minutes,
        id=EXPIRE_SUBSCRIPTIONS_JOB_ID,
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Started subscription-expiration scheduler (every %d minutes)",
        settings.expiration_check_interval_minutes,
    )


def shutdown_scheduler() -> None:
    """Stop the scheduler. Safe to call even if it was never started."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
