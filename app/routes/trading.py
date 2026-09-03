from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import SessionLocal

from app.core.dependencies import get_current_user

from app.models.user import User
from app.models.portfolio import Portfolio
from app.models.position import Position
from app.models.trade import Trade
from app.models.order import Order
from app.models.portfolio_snapshot import PortfolioSnapshot

from app.schemas.trade import TradeCreate

from app.services.market_service import get_stock_price
from app.services.order_service import check_pending_orders


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
# LIMIT ORDER HELPER
# =========================================================

def validate_limit_price(
    side: str,
    current_price: float,
    limit_price: float,
):
    """
    LIMIT BUY:
        Executes when market price <= limit price.

    LIMIT SELL:
        Executes when market price >= limit price.
    """

    if side == "BUY":
        return current_price <= limit_price

    if side == "SELL":
        return current_price >= limit_price

    return False


# =========================================================
# STOP ORDER HELPER
# =========================================================

def validate_stop_price(
    side: str,
    current_price: float,
    stop_price: float,
):
    """
    STOP BUY:
        Triggers when market price >= stop price.

    STOP SELL:
        Triggers when market price <= stop price.
    """

    if side == "BUY":
        return current_price >= stop_price

    if side == "SELL":
        return current_price <= stop_price

    return False


# =========================================================
# EXECUTE TRADE
# =========================================================

@router.post("/trade")
def execute_trade(
    trade: TradeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_id = current_user.id

    # -----------------------------------------------------
    # Normalize
    # -----------------------------------------------------

    symbol = trade.symbol.strip().upper()
    side = trade.side.strip().upper()
    order_type = trade.order_type.strip().upper()

    # -----------------------------------------------------
    # Validate symbol
    # -----------------------------------------------------

    if not symbol:
        raise HTTPException(
            status_code=400,
            detail="Stock symbol is required",
        )

    # -----------------------------------------------------
    # Validate side
    # -----------------------------------------------------

    if side not in {"BUY", "SELL"}:
        raise HTTPException(
            status_code=400,
            detail="Trade side must be BUY or SELL",
        )

    # -----------------------------------------------------
    # Validate quantity
    # -----------------------------------------------------

    if trade.quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero",
        )

    # -----------------------------------------------------
    # Validate order type
    # -----------------------------------------------------

    if order_type not in {
        "MARKET",
        "LIMIT",
        "STOP",
    }:
        raise HTTPException(
            status_code=400,
            detail="Order type must be MARKET, LIMIT or STOP",
        )

    # -----------------------------------------------------
    # Validate LIMIT price
    # -----------------------------------------------------

    if order_type == "LIMIT":

        if trade.limit_price is None:
            raise HTTPException(
                status_code=400,
                detail="Limit price is required for LIMIT orders",
            )

        if trade.limit_price <= 0:
            raise HTTPException(
                status_code=400,
                detail="Limit price must be greater than zero",
            )

    # -----------------------------------------------------
    # Validate STOP price
    # -----------------------------------------------------

    if order_type == "STOP":

        if trade.stop_price is None:
            raise HTTPException(
                status_code=400,
                detail="Stop price is required for STOP orders",
            )

        if trade.stop_price <= 0:
            raise HTTPException(
                status_code=400,
                detail="Stop price must be greater than zero",
            )

    # -----------------------------------------------------
    # Get current market price
    # -----------------------------------------------------

    current_price = get_stock_price(symbol)

    if current_price is None or current_price <= 0:
        raise HTTPException(
            status_code=400,
            detail="Unable to retrieve valid stock price",
        )

    # =====================================================
    # GET / CREATE PORTFOLIO
    # =====================================================

    portfolio = (
        db.query(Portfolio)
        .filter(
            Portfolio.user_id == user_id
        )
        .first()
    )

    if not portfolio:

        portfolio = Portfolio(
            user_id=user_id
        )

        db.add(portfolio)
        db.flush()

    # =====================================================
    # STOP ORDER
    # =====================================================

    if order_type == "STOP":

        stop_price = float(
            trade.stop_price
        )

        # -------------------------------------------------
        # Validate BUY funds
        # -------------------------------------------------

        if side == "BUY":

            required_value = (
                trade.quantity
                * stop_price
            )

            if portfolio.balance < required_value:

                raise HTTPException(
                    status_code=400,
                    detail="Not enough balance for stop order",
                )

        # -------------------------------------------------
        # Validate SELL position
        # -------------------------------------------------

        if side == "SELL":

            position = (
                db.query(Position)
                .filter(
                    Position.user_id == user_id,
                    Position.symbol == symbol,
                )
                .first()
            )

            if not position:

                raise HTTPException(
                    status_code=400,
                    detail="You do not own this stock",
                )

            if position.quantity < trade.quantity:

                raise HTTPException(
                    status_code=400,
                    detail="Not enough shares",
                )

        # -------------------------------------------------
        # Create STOP order
        # -------------------------------------------------

        new_order = Order(
            user_id=user_id,
            symbol=symbol,
            quantity=trade.quantity,
            side=side,
            order_type="STOP",
            stop_price=stop_price,
            status="PENDING",
            created_at=datetime.utcnow(),
        )

        db.add(new_order)

        try:

            db.commit()

        except Exception:

            db.rollback()

            raise HTTPException(
                status_code=500,
                detail="Stop order could not be created",
            )

        return {
            "message": "Stop order placed",
            "order_id": new_order.id,
            "symbol": symbol,
            "side": side,
            "order_type": "STOP",
            "status": "PENDING",
            "quantity": trade.quantity,
            "stop_price": stop_price,
            "current_price": current_price,
        }

    # =====================================================
    # LIMIT ORDER
    # =====================================================

    if order_type == "LIMIT":

        limit_price = float(
            trade.limit_price
        )

        can_execute = validate_limit_price(
            side,
            current_price,
            limit_price,
        )

        # -------------------------------------------------
        # Validate BUY funds
        # -------------------------------------------------

        if side == "BUY":

            required_value = (
                trade.quantity
                * limit_price
            )

            if portfolio.balance < required_value:

                raise HTTPException(
                    status_code=400,
                    detail="Not enough balance for limit order",
                )

        # -------------------------------------------------
        # Validate SELL position
        # -------------------------------------------------

        if side == "SELL":

            position = (
                db.query(Position)
                .filter(
                    Position.user_id == user_id,
                    Position.symbol == symbol,
                )
                .first()
            )

            if not position:

                raise HTTPException(
                    status_code=400,
                    detail="You do not own this stock",
                )

            if position.quantity < trade.quantity:

                raise HTTPException(
                    status_code=400,
                    detail="Not enough shares",
                )

        # =================================================
        # LIMIT ORDER — IMMEDIATE EXECUTION
        # =================================================

        if can_execute:

            execution_price = current_price

            cost = (
                trade.quantity
                * execution_price
            )

            avg_cost = None
            realized_pnl = 0

            # ---------------------------------------------
            # BUY
            # ---------------------------------------------

            if side == "BUY":

                if portfolio.balance < cost:

                    raise HTTPException(
                        status_code=400,
                        detail="Not enough balance",
                    )

                portfolio.balance -= cost

                position = (
                    db.query(Position)
                    .filter(
                        Position.user_id == user_id,
                        Position.symbol == symbol,
                    )
                    .first()
                )

                if position:

                    total_quantity = (
                        position.quantity
                        + trade.quantity
                    )

                    total_cost = (
                        position.avg_price
                        * position.quantity
                    ) + cost

                    position.avg_price = (
                        total_cost
                        / total_quantity
                    )

                    position.quantity = (
                        total_quantity
                    )

                else:

                    position = Position(
                        user_id=user_id,
                        symbol=symbol,
                        quantity=trade.quantity,
                        avg_price=execution_price,
                    )

                    db.add(position)

            # ---------------------------------------------
            # SELL
            # ---------------------------------------------

            else:

                position = (
                    db.query(Position)
                    .filter(
                        Position.user_id == user_id,
                        Position.symbol == symbol,
                    )
                    .first()
                )

                if not position:

                    raise HTTPException(
                        status_code=400,
                        detail="You do not own this stock",
                    )

                if position.quantity < trade.quantity:

                    raise HTTPException(
                        status_code=400,
                        detail="Not enough shares",
                    )

                avg_cost = position.avg_price

                realized_pnl = (
                    execution_price
                    - avg_cost
                ) * trade.quantity

                portfolio.balance += cost

                position.quantity -= trade.quantity

                if position.quantity == 0:

                    db.delete(position)

            # ---------------------------------------------
            # ORDER
            # ---------------------------------------------

            now = datetime.utcnow()

            new_order = Order(
                user_id=user_id,
                symbol=symbol,
                quantity=trade.quantity,
                side=side,
                order_type="LIMIT",
                limit_price=limit_price,
                status="FILLED",
                filled_price=execution_price,
                created_at=now,
                filled_at=now,
            )

            db.add(new_order)

            # ---------------------------------------------
            # TRADE
            # ---------------------------------------------

            new_trade = Trade(
                user_id=user_id,
                symbol=symbol,
                quantity=trade.quantity,
                price=execution_price,
                side=side,
                order_type="LIMIT",
                avg_cost=avg_cost,
                realized_pnl=realized_pnl,
            )

            db.add(new_trade)

            # ---------------------------------------------
            # SNAPSHOT
            # ---------------------------------------------

            positions = (
                db.query(Position)
                .filter(
                    Position.user_id == user_id
                )
                .all()
            )

            portfolio_value = portfolio.balance

            for position in positions:

                price = get_stock_price(
                    position.symbol
                )

                if price:

                    portfolio_value += (
                        position.quantity
                        * price
                    )

            snapshot = PortfolioSnapshot(
                user_id=user_id,
                total_value=portfolio_value,
            )

            db.add(snapshot)

            try:

                db.commit()

            except Exception:

                db.rollback()

                raise HTTPException(
                    status_code=500,
                    detail="Limit order could not be completed",
                )

            return {
                "message": "Limit order executed immediately",
                "order_id": new_order.id,
                "symbol": symbol,
                "side": side,
                "order_type": "LIMIT",
                "status": "FILLED",
                "quantity": trade.quantity,
                "limit_price": limit_price,
                "filled_price": execution_price,
                "realized_pnl": realized_pnl,
            }

        # =================================================
        # LIMIT ORDER — PENDING
        # =================================================

        new_order = Order(
            user_id=user_id,
            symbol=symbol,
            quantity=trade.quantity,
            side=side,
            order_type="LIMIT",
            limit_price=limit_price,
            status="PENDING",
            created_at=datetime.utcnow(),
        )

        db.add(new_order)

        try:

            db.commit()

        except Exception:

            db.rollback()

            raise HTTPException(
                status_code=500,
                detail="Limit order could not be created",
            )

        return {
            "message": "Limit order placed",
            "order_id": new_order.id,
            "symbol": symbol,
            "side": side,
            "order_type": "LIMIT",
            "status": "PENDING",
            "quantity": trade.quantity,
            "limit_price": limit_price,
            "current_price": current_price,
        }

    # =====================================================
    # MARKET ORDER
    # =====================================================

    cost = (
        trade.quantity
        * current_price
    )

    avg_cost = None
    realized_pnl = 0

    # -----------------------------------------------------
    # BUY
    # -----------------------------------------------------

    if side == "BUY":

        if portfolio.balance < cost:

            raise HTTPException(
                status_code=400,
                detail="Not enough balance",
            )

        portfolio.balance -= cost

        position = (
            db.query(Position)
            .filter(
                Position.user_id == user_id,
                Position.symbol == symbol,
            )
            .first()
        )

        if position:

            total_quantity = (
                position.quantity
                + trade.quantity
            )

            total_cost = (
                position.avg_price
                * position.quantity
            ) + cost

            position.avg_price = (
                total_cost
                / total_quantity
            )

            position.quantity = total_quantity

        else:

            position = Position(
                user_id=user_id,
                symbol=symbol,
                quantity=trade.quantity,
                avg_price=current_price,
            )

            db.add(position)

    # -----------------------------------------------------
    # SELL
    # -----------------------------------------------------

    else:

        position = (
            db.query(Position)
            .filter(
                Position.user_id == user_id,
                Position.symbol == symbol,
            )
            .first()
        )

        if not position:

            raise HTTPException(
                status_code=400,
                detail="You do not own this stock",
            )

        if position.quantity < trade.quantity:

            raise HTTPException(
                status_code=400,
                detail="Not enough shares",
            )

        avg_cost = position.avg_price

        realized_pnl = (
            current_price
            - avg_cost
        ) * trade.quantity

        portfolio.balance += cost

        position.quantity -= trade.quantity

        if position.quantity == 0:

            db.delete(position)

    # -----------------------------------------------------
    # MARKET ORDER RECORD
    # -----------------------------------------------------

    now = datetime.utcnow()

    new_order = Order(
        user_id=user_id,
        symbol=symbol,
        quantity=trade.quantity,
        side=side,
        order_type="MARKET",
        status="FILLED",
        filled_price=current_price,
        created_at=now,
        filled_at=now,
    )

    db.add(new_order)

    # -----------------------------------------------------
    # TRADE RECORD
    # -----------------------------------------------------

    new_trade = Trade(
        user_id=user_id,
        symbol=symbol,
        quantity=trade.quantity,
        price=current_price,
        side=side,
        order_type="MARKET",
        avg_cost=avg_cost,
        realized_pnl=realized_pnl,
    )

    db.add(new_trade)

    # -----------------------------------------------------
    # PORTFOLIO SNAPSHOT
    # -----------------------------------------------------

    positions = (
        db.query(Position)
        .filter(
            Position.user_id == user_id
        )
        .all()
    )

    portfolio_value = portfolio.balance

    for position in positions:

        price = get_stock_price(
            position.symbol
        )

        if price:

            portfolio_value += (
                position.quantity
                * price
            )

    snapshot = PortfolioSnapshot(
        user_id=user_id,
        total_value=portfolio_value,
    )

    db.add(snapshot)

    # -----------------------------------------------------
    # COMMIT
    # -----------------------------------------------------

    try:

        db.commit()

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Trade could not be completed",
        )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "message": "Trade executed successfully",
        "order_id": new_order.id,
        "symbol": symbol,
        "side": side,
        "order_type": "MARKET",
        "status": "FILLED",
        "quantity": trade.quantity,
        "price_used": current_price,
        "total_value": cost,
        "realized_pnl": realized_pnl,
    }


# =========================================================
# CHECK PENDING ORDERS
# =========================================================

@router.post("/orders/check")
def check_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    results = check_pending_orders(
        current_user.id,
        db,
    )

    return {
        "checked": True,
        "filled_count": len(results),
        "filled_orders": results,
    }


# =========================================================
# CANCEL ORDER
# =========================================================

@router.post("/orders/{order_id}/cancel")
def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = (
        db.query(Order)
        .filter(
            Order.id == order_id,
            Order.user_id == current_user.id,
        )
        .first()
    )

    if not order:

        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    if order.status != "PENDING":

        raise HTTPException(
            status_code=400,
            detail="Only pending orders can be cancelled",
        )

    order.status = "CANCELLED"
    order.cancelled_at = datetime.utcnow()

    try:

        db.commit()

    except Exception:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Order could not be cancelled",
        )

    return {
        "message": "Order cancelled successfully",
        "order_id": order.id,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": order.quantity,
        "order_type": order.order_type,
        "status": order.status,
    }


# =========================================================
# GET ALL ORDERS
# =========================================================

@router.get("/orders")
def get_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orders = (
        db.query(Order)
        .filter(
            Order.user_id == current_user.id
        )
        .order_by(
            Order.created_at.desc()
        )
        .all()
    )

    return [
        {
            "id": order.id,
            "symbol": order.symbol,
            "quantity": order.quantity,
            "side": order.side,
            "order_type": order.order_type,
            "limit_price": order.limit_price,
            "stop_price": order.stop_price,
            "status": order.status,
            "filled_price": order.filled_price,
            "created_at": order.created_at,
            "filled_at": order.filled_at,
            "cancelled_at": order.cancelled_at,
        }
        for order in orders
    ]


# =========================================================
# TRADE HISTORY
# =========================================================

@router.get("/history")
def get_trade_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    trades = (
        db.query(Trade)
        .filter(
            Trade.user_id == current_user.id
        )
        .order_by(
            Trade.id.desc()
        )
        .all()
    )

    return [
        {
            "id": trade.id,
            "symbol": trade.symbol,
            "quantity": trade.quantity,
            "price": trade.price,
            "side": trade.side,
            "order_type": trade.order_type,
            "avg_cost": trade.avg_cost,
            "realized_pnl": trade.realized_pnl,
            "created_at": trade.created_at,
        }
        for trade in trades
    ]