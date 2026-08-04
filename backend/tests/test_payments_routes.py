import json

import respx
from httpx import Response

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models import Guild, SubscriptionTier, TierRoleMapping, User
from app.models.enums import BillingPeriod

settings = get_settings()
PAYPAL_BASE_URL = "https://api-m.sandbox.paypal.com"
NOWPAYMENTS_BASE_URL = "https://api.nowpayments.io/v1"


async def _seed_guild_tier_user(db_session):
    guild = Guild(guild_id="111", guild_name="Test Guild")
    user = User(discord_id="222", username="tester")
    db_session.add_all([guild, user])
    await db_session.flush()

    tier = SubscriptionTier(
        guild_id=guild.id,
        name="Gold",
        price=10,
        currency="USD",
        billing_period=BillingPeriod.MONTHLY,
        duration_days=30,
    )
    db_session.add(tier)
    await db_session.flush()

    mapping = TierRoleMapping(guild_id=guild.id, tier_id=tier.id, discord_role_id="333")
    db_session.add(mapping)
    await db_session.commit()

    return guild, tier, user


async def _login(client, user):
    client.cookies.set("session", create_access_token(user.id))


async def test_paypal_checkout_requires_authentication(client, db_session):
    _, tier, _ = await _seed_guild_tier_user(db_session)

    response = await client.post(f"/payments/paypal/checkout/{tier.id}")

    assert response.status_code == 401


@respx.mock
async def test_paypal_checkout_creates_pending_payment_and_returns_url(client, db_session):
    _, tier, user = await _seed_guild_tier_user(db_session)
    await _login(client, user)

    respx.post(f"{PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok"})
    )
    respx.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders").mock(
        return_value=Response(
            201,
            json={
                "id": "ORDER123",
                "links": [{"rel": "approve", "href": "https://paypal.com/checkoutnow?token=ORDER123"}],
            },
        )
    )

    response = await client.post(f"/payments/paypal/checkout/{tier.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["checkout_url"] == "https://paypal.com/checkoutnow?token=ORDER123"


@respx.mock
async def test_paypal_webhook_activates_subscription_and_assigns_role(client, db_session):
    guild, tier, user = await _seed_guild_tier_user(db_session)
    await _login(client, user)

    respx.post(f"{PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok"})
    )
    respx.post(f"{PAYPAL_BASE_URL}/v2/checkout/orders").mock(
        return_value=Response(
            201,
            json={
                "id": "ORDER123",
                "links": [{"rel": "approve", "href": "https://paypal.com/checkoutnow?token=ORDER123"}],
            },
        )
    )
    checkout_response = await client.post(f"/payments/paypal/checkout/{tier.id}")
    assert checkout_response.status_code == 200

    settings.paypal_webhook_id = "wh-1"
    respx.post(f"{PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature").mock(
        return_value=Response(200, json={"verification_status": "SUCCESS"})
    )
    role_route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": True}, "error": None})
    )

    webhook_payload = {
        "id": "evt-1",
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAPTURE1",
            "supplementary_data": {"related_ids": {"order_id": "ORDER123"}},
        },
    }
    webhook_response = await client.post(
        "/webhooks/paypal",
        content=json.dumps(webhook_payload),
        headers={
            "paypal-transmission-id": "tx-1",
            "paypal-transmission-time": "2026-01-01T00:00:00Z",
            "paypal-cert-url": "https://api.paypal.com/cert",
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-transmission-sig": "sig",
        },
    )

    assert webhook_response.status_code == 200
    assert role_route.called

    settings.paypal_webhook_id = ""


@respx.mock
async def test_paypal_webhook_rejects_invalid_signature(client, db_session):
    settings.paypal_webhook_id = "wh-1"
    respx.post(f"{PAYPAL_BASE_URL}/v1/oauth2/token").mock(
        return_value=Response(200, json={"access_token": "tok"})
    )
    respx.post(f"{PAYPAL_BASE_URL}/v1/notifications/verify-webhook-signature").mock(
        return_value=Response(200, json={"verification_status": "FAILURE"})
    )

    response = await client.post(
        "/webhooks/paypal",
        content=json.dumps({"id": "evt-1", "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {}}),
        headers={
            "paypal-transmission-id": "tx-1",
            "paypal-transmission-time": "2026-01-01T00:00:00Z",
            "paypal-cert-url": "https://api.paypal.com/cert",
            "paypal-auth-algo": "SHA256withRSA",
            "paypal-transmission-sig": "sig",
        },
    )

    assert response.status_code == 400
    settings.paypal_webhook_id = ""


async def test_crypto_checkout_requires_authentication(client, db_session):
    _, tier, _ = await _seed_guild_tier_user(db_session)

    response = await client.post(f"/payments/crypto/checkout/{tier.id}")

    assert response.status_code == 401


@respx.mock
async def test_crypto_checkout_creates_pending_payment_and_returns_url(client, db_session):
    _, tier, user = await _seed_guild_tier_user(db_session)
    await _login(client, user)

    respx.post(f"{NOWPAYMENTS_BASE_URL}/invoice").mock(
        return_value=Response(
            201, json={"id": "INV123", "invoice_url": "https://nowpayments.io/payment/INV123"}
        )
    )

    response = await client.post(f"/payments/crypto/checkout/{tier.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["checkout_url"] == "https://nowpayments.io/payment/INV123"


@respx.mock
async def test_nowpayments_webhook_activates_subscription_and_assigns_role(client, db_session):
    guild, tier, user = await _seed_guild_tier_user(db_session)
    await _login(client, user)

    respx.post(f"{NOWPAYMENTS_BASE_URL}/invoice").mock(
        return_value=Response(
            201, json={"id": "INV123", "invoice_url": "https://nowpayments.io/payment/INV123"}
        )
    )
    checkout_response = await client.post(f"/payments/crypto/checkout/{tier.id}")
    assert checkout_response.status_code == 200
    payment_reference = checkout_response.json()["data"]["payment_id"]

    settings.nowpayments_ipn_secret = "test-ipn-secret"

    import hashlib
    import hmac

    from sqlalchemy import select

    from app.models import Payment

    result = await db_session.execute(select(Payment).where(Payment.id == payment_reference))
    payment = result.scalar_one()
    order_id = payment.provider_transaction_id

    payload = {"payment_id": 999, "payment_status": "finished", "order_id": order_id}
    sorted_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(
        settings.nowpayments_ipn_secret.encode(), sorted_payload.encode(), hashlib.sha512
    ).hexdigest()

    role_route = respx.post(f"{settings.bot_internal_api_url}/internal/roles/assign").mock(
        return_value=Response(200, json={"success": True, "data": {"assigned": True}, "error": None})
    )

    webhook_response = await client.post(
        "/webhooks/nowpayments",
        content=json.dumps(payload),
        headers={"x-nowpayments-sig": signature},
    )

    assert webhook_response.status_code == 200
    assert role_route.called

    settings.nowpayments_ipn_secret = ""
