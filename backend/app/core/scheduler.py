"""Wires the periodic subscription-expiration sweep into APScheduler."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.jobs.expire_subscriptions import expire_due_subscriptions

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

EXPIRE_SUBSCRIPTIONS_JOB_ID = "expire_subscriptions"

# Arbitrary constant key for a Postgres advisory lock. Production runs the backend
# with multiple uvicorn workers (see docker-compose.prod.yml), and each worker's
# process has its own in-memory APScheduler, so every worker would otherwise run
# this sweep on the same schedule. The lock lets only one worker's tick actually
# do the work; the others no-op for that tick. Requires a session-scoped Postgres
# connection (true for Supabase's session pooler) — a transaction-pooled
# connection would not hold the lock across statements.
EXPIRE_SUBSCRIPTIONS_LOCK_KEY = 872_364_501


async def _run_expire_subscriptions_job() -> None:
    async with AsyncSessionLocal() as db:
        acquired = (
            await db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": EXPIRE_SUBSCRIPTIONS_LOCK_KEY})
        ).scalar()
        if not acquired:
            logger.debug("Another worker is already running the expiration sweep; skipping this tick")
            return

        try:
            expired_count = await expire_due_subscriptions(db)
            if expired_count:
                logger.info("Expired %d subscription(s)", expired_count)
        finally:
            await db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": EXPIRE_SUBSCRIPTIONS_LOCK_KEY})


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
