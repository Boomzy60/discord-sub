import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.payments.paypal import ORDER_APPROVED_EVENT, PayPalAPIError, PayPalProvider
from app.services.subscription_service import record_and_apply_webhook_event

router = APIRouter(tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/webhooks/paypal")
async def paypal_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    body = await request.body()
    headers = dict(request.headers)
    provider = PayPalProvider()

    if not await provider.verify_webhook(headers, body):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature")

    event = provider.parse_webhook_event(headers, body)

    if event.event_type == ORDER_APPROVED_EVENT:
        order_id = event.raw_payload.get("resource", {}).get("id")
        if order_id:
            try:
                await provider.capture_order(order_id)
            except PayPalAPIError as exc:
                logger.error("Failed to capture PayPal order %s: %s", order_id, exc)
        return {"success": True, "data": None, "error": None}

    await record_and_apply_webhook_event(db, provider.name, event)
    return {"success": True, "data": None, "error": None}
