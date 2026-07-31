from datetime import datetime, timedelta
from app.models.portfolio_snapshot import PortfolioSnapshot
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.portfolio import Portfolio
from app.models.position import Position
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.market_service import get_stock_price

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/")
def get_portfolio(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.id

    portfolio = db.query(Portfolio).filter(Portfolio.user_id == user_id).first()
    positions = db.query(Position).filter(Position.user_id == user_id).all()

    total_value = portfolio.balance if portfolio else 0
    position_data = []

    for pos in positions:
        current_price = get_stock_price(pos.symbol)

        if current_price is None:
            continue

        value = pos.quantity * current_price
        pnl = (current_price - pos.avg_price) * pos.quantity

        total_value += value

        position_data.append({
            "symbol": pos.symbol,
            "quantity": pos.quantity,
            "avg_price": pos.avg_price,
            "current_price": current_price,
            "value": value,
            "pnl": pnl
        })

    return {
        "cash": portfolio.balance if portfolio else 0,
        "total_value": total_value,
        "positions": position_data
    }
@router.get("/performance")
def get_portfolio_performance(
    period: str = "ALL",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = (
        db.query(PortfolioSnapshot)
        .filter(
            PortfolioSnapshot.user_id == current_user.id
        )
    )

    now = datetime.utcnow()

    if period == "1Y":
        cutoff = now - timedelta(days=365)
        query = query.filter(PortfolioSnapshot.created_at >= cutoff)

    elif period == "3M":
        cutoff = now - timedelta(days=90)
        query = query.filter(PortfolioSnapshot.created_at >= cutoff)

    elif period == "1M":
        cutoff = now - timedelta(days=30)
        query = query.filter(PortfolioSnapshot.created_at >= cutoff)

    elif period == "1W":
        cutoff = now - timedelta(days=7)
        query = query.filter(PortfolioSnapshot.created_at >= cutoff)

    elif period == "1D":
        cutoff = now - timedelta(days=1)
        query = query.filter(PortfolioSnapshot.created_at >= cutoff)

    snapshots = (
        query
        .order_by(PortfolioSnapshot.created_at.asc())
        .all()
    )

    return [
        {
            "value": snapshot.total_value,
            "date": snapshot.created_at.strftime("%d/%m %H:%M"),
        }
        for snapshot in snapshots
    ]