import truststore

# Verify outbound TLS (Discord/PayPal/NOWPayments) against the OS certificate store instead
# of certifi's bundle. Needed on machines where a corporate proxy or antivirus does TLS
# inspection with a root CA that's trusted by Windows but not by certifi.
truststore.inject_into_ssl()

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    health,
    internal,
    payments_crypto,
    payments_paypal,
    tiers,
    webhooks_nowpayments,
    webhooks_paypal,
)
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.scheduler import shutdown_scheduler, start_scheduler

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Kiyomi Studio API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(tiers.router)
app.include_router(payments_paypal.router)
app.include_router(payments_crypto.router)
app.include_router(webhooks_paypal.router)
app.include_router(webhooks_nowpayments.router)
app.include_router(internal.router)
