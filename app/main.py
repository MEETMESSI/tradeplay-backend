import asyncio
from app.routes.notifications import router as notifications_router
from app.models.notification import Notification
from contextlib import asynccontextmanager

from dotenv import load_dotenv

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.db.database import engine, Base
from app.core.rate_limit import rate_limit_middleware

from app.services.order_worker import (
    pending_order_worker,
)

load_dotenv()


# -------------------------------------------------
# Models
# -------------------------------------------------

from app.models import (
    user,
    user_settings,
    portfolio,
    position,
    trade,
    watchlist,
    portfolio_snapshot,
    refresh_token,
    audit_log,
    password_reset_token,
    order,
)


# -------------------------------------------------
# Routes
# -------------------------------------------------

from app.routes import (
    auth,
    trading,
    portfolio,
    market,
    analytics,
    settings,
)


# -------------------------------------------------
# Background Worker
# -------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    worker = asyncio.create_task(
        pending_order_worker()
    )

    print(
        "Tradeplay pending-order worker started."
    )

    try:

        yield

    finally:

        worker.cancel()

        try:

            await worker

        except asyncio.CancelledError:

            pass

        print(
            "Tradeplay pending-order worker stopped."
        )


# -------------------------------------------------
# Create App
# -------------------------------------------------

app = FastAPI(
    title="Tradeplay API",
    lifespan=lifespan,
)


# -------------------------------------------------
# CORS
# -------------------------------------------------

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------
# Security Headers
# -------------------------------------------------

@app.middleware("http")
async def security_headers(
    request: Request,
    call_next,
):

    response: Response = await call_next(
        request
    )

    response.headers[
        "X-Content-Type-Options"
    ] = "nosniff"

    response.headers[
        "X-Frame-Options"
    ] = "DENY"

    response.headers[
        "Referrer-Policy"
    ] = (
        "strict-origin-when-cross-origin"
    )

    response.headers[
        "Permissions-Policy"
    ] = (
        "camera=(), microphone=(), "
        "geolocation=()"
    )

    return response


# -------------------------------------------------
# Rate Limiting
# -------------------------------------------------

app.middleware("http")(
    rate_limit_middleware
)


# -------------------------------------------------
# Database
# -------------------------------------------------

Base.metadata.create_all(
    bind=engine
)


# -------------------------------------------------
# Routes
# -------------------------------------------------

app.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"],
)

app.include_router(
    trading.router,
    prefix="/trade",
    tags=["Trading"],
)

app.include_router(
    portfolio.router,
    prefix="/portfolio",
    tags=["Portfolio"],
)

app.include_router(
    market.router,
    prefix="/market",
    tags=["Market"],
)

app.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["Analytics"],
)

app.include_router(
    settings.router,
    prefix="/settings",
    tags=["Settings"],
)

# -------------------------------------------------
# Root
# -------------------------------------------------

@app.get("/")
def root():

    return {
        "message":
        "Tradeplay backend is running 🚀"
    }

app.include_router(
    notifications_router,
    prefix="/notifications",
    tags=["Notifications"],
)