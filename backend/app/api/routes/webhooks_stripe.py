from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.payments.stripe_provider import StripeProvider
from app.services.subscription_service import record_and_apply_webhook_event

router = APIRouter(tags=["webhooks"])


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    body = await request.body()
    headers = dict(request.headers)
    provider = StripeProvider()

    if not await provider.verify_webhook(headers, body):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature")

    event = provider.parse_webhook_event(headers, body)
    await record_and_apply_webhook_event(db, provider.name, event)
    return {"success": True, "data": None, "error": None}
