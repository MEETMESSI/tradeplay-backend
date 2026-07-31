from app.models.portfolio_snapshot import PortfolioSnapshot
from app.services.market_service import get_stock_price
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.models.portfolio import Portfolio
from app.models.position import Position
from app.models.trade import Trade
from app.schemas.trade import TradeCreate
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/trade")
def execute_trade(
    trade: TradeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_id = current_user.id

    # Get live price
    price = get_stock_price(trade.symbol)

    if price is None:
        raise HTTPException(
            status_code=400,
            detail="Invalid stock symbol"
        )

    cost = trade.quantity * price

    avg_cost = None
    realized_pnl = 0

    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.user_id == user_id)
        .first()
    )

    if not portfolio:
        portfolio = Portfolio(user_id=user_id)
        db.add(portfolio)
        db.commit()
        db.refresh(portfolio)

    if trade.side == "BUY":

        if portfolio.balance < cost:
            raise HTTPException(
                status_code=400,
                detail="Not enough balance"
            )

        portfolio.balance -= cost

        position = (
            db.query(Position)
            .filter(
                Position.user_id == user_id,
                Position.symbol == trade.symbol
            )
            .first()
        )

        if position:
            total_qty = (
                position.quantity
                + trade.quantity
            )

            position.avg_price = (
                (
                    position.avg_price
                    * position.quantity
                    + cost
                )
                / total_qty
            )

            position.quantity = total_qty

        else:
            position = Position(
                user_id=user_id,
                symbol=trade.symbol,
                quantity=trade.quantity,
                avg_price=price
            )

            db.add(position)

    elif trade.side == "SELL":

        position = (
            db.query(Position)
            .filter(
                Position.user_id == user_id,
                Position.symbol == trade.symbol
            )
            .first()
        )

        if not position or position.quantity < trade.quantity:
            raise HTTPException(
                status_code=400,
                detail="Not enough shares"
            )

        avg_cost = position.avg_price

        realized_pnl = (
            (price - avg_cost)
            * trade.quantity
        )

        portfolio.balance += cost

        position.quantity -= trade.quantity

        if position.quantity == 0:
            db.delete(position)

    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid trade type"
        )

    new_trade = Trade(
        user_id=user_id,
        symbol=trade.symbol,
        quantity=trade.quantity,
        price=price,
        side=trade.side,
        avg_cost=avg_cost,
        realized_pnl=realized_pnl
    )

    db.add(new_trade)
    db.commit()

    # Portfolio snapshot
    positions = (
        db.query(Position)
        .filter(Position.user_id == user_id)
        .all()
    )

    portfolio_value = portfolio.balance

    for pos in positions:
        current_price = get_stock_price(pos.symbol)

        if current_price:
            portfolio_value += (
                pos.quantity
                * current_price
            )

    snapshot = PortfolioSnapshot(
        user_id=user_id,
        total_value=portfolio_value
    )

    db.add(snapshot)
    db.commit()

    return {
        "message": "Trade executed successfully",
        "price_used": price,
        "realized_pnl": realized_pnl
    }


@router.get("/history")
def get_trade_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    trades = (
        db.query(Trade)
        .filter(Trade.user_id == current_user.id)
        .order_by(Trade.id.desc())
        .all()
    )

    return [
        {
            "id": trade.id,
            "symbol": trade.symbol,
            "quantity": trade.quantity,
            "price": trade.price,
            "side": trade.side,
            "avg_cost": trade.avg_cost,
            "realized_pnl": trade.realized_pnl,
            "created_at": trade.created_at
        }
        for trade in trades
    ]