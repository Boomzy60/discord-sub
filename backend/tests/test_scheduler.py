import asyncio

from app.core.scheduler import EXPIRE_SUBSCRIPTIONS_JOB_ID, scheduler, shutdown_scheduler, start_scheduler


async def test_start_scheduler_registers_expiration_job():
    try:
        start_scheduler()
        job = scheduler.get_job(EXPIRE_SUBSCRIPTIONS_JOB_ID)
        assert job is not None
        assert scheduler.running
    finally:
        shutdown_scheduler()
        # AsyncIOScheduler.shutdown() defers via call_soon_threadsafe; give the
        # loop one tick to actually apply it before asserting on .running.
        await asyncio.sleep(0)

    assert not scheduler.running
