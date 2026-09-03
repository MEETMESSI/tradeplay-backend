from datetime import datetime, timedelta

from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.trade import Trade

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import SessionLocal

from app.models.portfolio import Portfolio
from app.models.position import Position
from app.core.dependencies import get_current_user
from app.models.user import User

from app.services.market_service import get_stock_price


router = APIRouter()


# =========================================================
# DATABASE
# =========================================================

def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =========================================================
# PORTFOLIO
# =========================================================

@router.get("/")
def get_portfolio(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id

    # -----------------------------------------------------
    # Get portfolio
    # -----------------------------------------------------

    portfolio = (
        db.query(Portfolio)
        .filter(
            Portfolio.user_id == user_id
        )
        .first()
    )

    # -----------------------------------------------------
    # Get positions
    # -----------------------------------------------------

    positions = (
        db.query(Position)
        .filter(
            Position.user_id == user_id
        )
        .all()
    )

    cash = (
        portfolio.balance
        if portfolio
        else 0
    )

    # -----------------------------------------------------
    # Calculate positions
    # -----------------------------------------------------

    position_data = []

    total_invested = 0
    total_market_value = 0
    total_unrealized_pnl = 0

    for pos in positions:

        current_price = get_stock_price(
            pos.symbol
        )

        if current_price is None:
            continue

        # -------------------------------------------------
        # Invested value
        # -------------------------------------------------

        invested_value = (
            pos.quantity
            * pos.avg_price
        )

        # -------------------------------------------------
        # Current market value
        # -------------------------------------------------

        market_value = (
            pos.quantity
            * current_price
        )

        # -------------------------------------------------
        # Unrealized P&L
        # -------------------------------------------------

        unrealized_pnl = (
            current_price
            - pos.avg_price
        ) * pos.quantity

        # -------------------------------------------------
        # Unrealized P&L %
        # -------------------------------------------------

        if invested_value > 0:

            unrealized_pnl_percent = (
                unrealized_pnl
                / invested_value
            ) * 100

        else:

            unrealized_pnl_percent = 0

        total_invested += invested_value
        total_market_value += market_value
        total_unrealized_pnl += unrealized_pnl

        position_data.append({
            "symbol": pos.symbol,
            "quantity": pos.quantity,
            "avg_price": pos.avg_price,
            "current_price": current_price,

            "invested_value": invested_value,
            "market_value": market_value,

            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_percent": (
                unrealized_pnl_percent
            ),
        })

    # -----------------------------------------------------
    # Portfolio total value
    # -----------------------------------------------------

    total_value = (
        cash
        + total_market_value
    )

    # -----------------------------------------------------
    # Allocation %
    #
    # Calculate only after total portfolio value
    # is known.
    # -----------------------------------------------------

    for position in position_data:

        if total_value > 0:

            position["allocation_percent"] = (
                position["market_value"]
                / total_value
            ) * 100

        else:

            position["allocation_percent"] = 0

    # -----------------------------------------------------
    # Realized P&L
    # -----------------------------------------------------

    realized_result = (
        db.query(Trade.realized_pnl)
        .filter(
            Trade.user_id == user_id
        )
        .all()
    )

    total_realized_pnl = sum(
        (row[0] or 0)
        for row in realized_result
    )

    # -----------------------------------------------------
    # Total P&L
    # -----------------------------------------------------

    total_pnl = (
        total_realized_pnl
        + total_unrealized_pnl
    )

    # -----------------------------------------------------
    # Total return %
    #
    # Based on current invested capital.
    # -----------------------------------------------------

    if total_invested > 0:

        total_pnl_percent = (
            total_pnl
            / total_invested
        ) * 100

    else:

        total_pnl_percent = 0

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

    return {
        "cash": cash,

        "total_value": total_value,

        "total_invested": total_invested,
        "total_market_value": total_market_value,

        "total_unrealized_pnl": (
            total_unrealized_pnl
        ),

        "total_realized_pnl": (
            total_realized_pnl
        ),

        "total_pnl": total_pnl,

        "total_pnl_percent": (
            total_pnl_percent
        ),

        "positions": position_data,
    }


# =========================================================
# PORTFOLIO PERFORMANCE
# =========================================================

@router.get("/performance")
def get_portfolio_performance(
    period: str = "ALL",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(PortfolioSnapshot)
        .filter(
            PortfolioSnapshot.user_id
            == current_user.id
        )
    )

    now = datetime.utcnow()

    if period == "1Y":

        cutoff = (
            now - timedelta(days=365)
        )

        query = query.filter(
            PortfolioSnapshot.created_at
            >= cutoff
        )

    elif period == "3M":

        cutoff = (
            now - timedelta(days=90)
        )

        query = query.filter(
            PortfolioSnapshot.created_at
            >= cutoff
        )

    elif period == "1M":

        cutoff = (
            now - timedelta(days=30)
        )

        query = query.filter(
            PortfolioSnapshot.created_at
            >= cutoff
        )

    elif period == "1W":

        cutoff = (
            now - timedelta(days=7)
        )

        query = query.filter(
            PortfolioSnapshot.created_at
            >= cutoff
        )

    elif period == "1D":

        cutoff = (
            now - timedelta(days=1)
        )

        query = query.filter(
            PortfolioSnapshot.created_at
            >= cutoff
        )

    snapshots = (
        query
        .order_by(
            PortfolioSnapshot.created_at.asc()
        )
        .all()
    )

    return [
        {
            "value": snapshot.total_value,
            "date": snapshot.created_at.strftime(
                "%d/%m %H:%M"
            ),
        }
        for snapshot in snapshots
    ]