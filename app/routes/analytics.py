from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.core.dependencies import get_current_user
from app.models.user import User

from app.services.analytics_service import (
    get_trade_stats,
    get_portfolio_history,
    get_portfolio_allocation,
    get_sector_allocation,
    get_monthly_returns,
)

from app.services.analytics.risk import (
    get_risk_metrics,
)


router = APIRouter()


def get_db():
    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# =========================================================
# TRADE STATISTICS
# =========================================================

@router.get("/trade-stats")
def trade_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_trade_stats(
        current_user.id,
        db
    )


# =========================================================
# PORTFOLIO PERFORMANCE
# =========================================================

@router.get("/performance")
def portfolio_performance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_portfolio_history(
        current_user.id,
        db
    )


# =========================================================
# PORTFOLIO ALLOCATION
# =========================================================

@router.get("/allocation")
def portfolio_allocation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_portfolio_allocation(
        current_user.id,
        db
    )


# =========================================================
# SECTOR ALLOCATION
# =========================================================

@router.get("/sectors")
def sector_allocation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_sector_allocation(
        current_user.id,
        db
    )


# =========================================================
# MONTHLY RETURNS
# =========================================================

@router.get("/monthly-returns")
def monthly_returns(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_monthly_returns(
        current_user.id,
        db
    )


# =========================================================
# RISK METRICS
# =========================================================

@router.get("/risk")
def risk_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_risk_metrics(
        current_user.id,
        db
    )