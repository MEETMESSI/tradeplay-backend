from datetime import datetime

from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.portfolio import Portfolio
from app.models.position import Position
from app.models.trade import Trade
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.notification import Notification

from app.services.market_service import get_stock_price


def check_pending_orders(
    user_id: int,
    db: Session,
):
    """
    Check all pending LIMIT and STOP orders for a user.

    Each unique symbol is priced only once per worker cycle.

    LIMIT BUY:
        Executes when market price <= limit price.

    LIMIT SELL:
        Executes when market price >= limit price.

    STOP BUY:
        Executes when market price >= stop price.

    STOP SELL:
        Executes when market price <= stop price.
    """

    # =====================================================
    # GET PENDING ORDERS
    # =====================================================

    orders = (
        db.query(Order)
        .filter(
            Order.user_id == user_id,
            Order.status == "PENDING",
            Order.order_type.in_(["LIMIT", "STOP"]),
        )
        .order_by(Order.created_at.asc())
        .all()
    )

    results = []

    if not orders:
        return results

    # =====================================================
    # GET PORTFOLIO
    # =====================================================

    portfolio = (
        db.query(Portfolio)
        .filter(
            Portfolio.user_id == user_id
        )
        .first()
    )

    if not portfolio:
        return results

    # =====================================================
    # FETCH EACH UNIQUE SYMBOL ONLY ONCE
    # =====================================================

    symbols = {
        order.symbol.upper().strip()
        for order in orders
        if order.symbol
    }

    price_cache = {}

    for symbol in symbols:

        try:
            price = get_stock_price(symbol)

            if price is not None:
                price_cache[symbol] = float(price)

            else:
                price_cache[symbol] = None

        except Exception as e:

            print(
                f"[ORDER WORKER] PRICE ERROR "
                f"{symbol}: {e}"
            )

            price_cache[symbol] = None

    # =====================================================
    # CHECK ORDERS
    # =====================================================

    for order in orders:

        symbol = (
            order.symbol
            .upper()
            .strip()
        )

        # =================================================
        # GET PRICE FROM THIS WORKER CYCLE'S CACHE
        # =================================================

        current_price = price_cache.get(
            symbol
        )

        if current_price is None:
            continue

        # =================================================
        # CHECK ORDER CONDITION
        # =================================================

        should_execute = False

        # =================================================
        # LIMIT ORDER
        # =================================================

        if order.order_type == "LIMIT":

            if order.limit_price is None:
                continue

            limit_price = float(
                order.limit_price
            )

            if (
                order.side == "BUY"
                and current_price <= limit_price
            ):

                should_execute = True

            elif (
                order.side == "SELL"
                and current_price >= limit_price
            ):

                should_execute = True

        # =================================================
        # STOP ORDER
        # =================================================

        elif order.order_type == "STOP":

            if order.stop_price is None:
                continue

            stop_price = float(
                order.stop_price
            )

            if (
                order.side == "BUY"
                and current_price >= stop_price
            ):

                should_execute = True

            elif (
                order.side == "SELL"
                and current_price <= stop_price
            ):

                should_execute = True

        # =================================================
        # CONDITION NOT MET
        # =================================================

        if not should_execute:
            continue

        # =================================================
        # EXECUTION PRICE
        # =================================================

        execution_price = float(
            current_price
        )

        quantity = float(
            order.quantity
        )

        trade_value = (
            quantity
            * execution_price
        )

        avg_cost = None
        realized_pnl = 0

        # =================================================
        # BUY
        # =================================================

        if order.side == "BUY":

            # Re-check available cash.
            # Another order may have already used some cash
            # earlier in this same worker cycle.

            if float(
                portfolio.balance
            ) < trade_value:

                continue

            portfolio.balance = (
                float(portfolio.balance)
                - trade_value
            )

            position = (
                db.query(Position)
                .filter(
                    Position.user_id == user_id,
                    Position.symbol == symbol,
                )
                .first()
            )

            if position:

                old_quantity = float(
                    position.quantity
                )

                total_quantity = (
                    old_quantity
                    + quantity
                )

                total_cost = (
                    float(position.avg_price)
                    * old_quantity
                ) + trade_value

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
                    quantity=quantity,
                    avg_price=execution_price,
                )

                db.add(position)

        # =================================================
        # SELL
        # =================================================

        elif order.side == "SELL":

            position = (
                db.query(Position)
                .filter(
                    Position.user_id == user_id,
                    Position.symbol == symbol,
                )
                .first()
            )

            # Position may have already been sold.

            if not position:
                continue

            position_quantity = float(
                position.quantity
            )

            if position_quantity < quantity:
                continue

            avg_cost = float(
                position.avg_price
            )

            realized_pnl = (
                execution_price
                - avg_cost
            ) * quantity

            portfolio.balance = (
                float(portfolio.balance)
                + trade_value
            )

            position.quantity = (
                position_quantity
                - quantity
            )

            if float(
                position.quantity
            ) <= 0:

                db.delete(
                    position
                )

        # =================================================
        # UPDATE ORDER
        # =================================================

        now = datetime.utcnow()

        order.status = "FILLED"

        order.filled_price = (
            execution_price
        )

        order.filled_at = now

        # =================================================
        # CREATE TRADE
        # =================================================

        new_trade = Trade(
            user_id=user_id,
            symbol=symbol,
            quantity=quantity,
            price=execution_price,
            side=order.side,
            avg_cost=avg_cost,
            realized_pnl=realized_pnl,
        )

        db.add(
            new_trade
        )

        # =================================================
        # CREATE NOTIFICATION
        # =================================================

        notification_title = (
            f"{symbol} "
            f"{order.side} "
            f"Order Filled"
        )

        notification_message = (
            f"Your {order.order_type} "
            f"{order.side} order for "
            f"{quantity:g} share(s) of "
            f"{symbol} was filled at "
            f"${execution_price:.2f}."
        )

        if order.side == "SELL":

            notification_message += (
                f" Realized P&L: "
                f"${realized_pnl:.2f}."
            )

        notification = Notification(
            user_id=user_id,
            title=notification_title,
            message=notification_message,
            notification_type="ORDER",
            is_read=False,
        )

        db.add(
            notification
        )

        # =================================================
        # RESULT
        # =================================================

        result = {
            "order_id": order.id,
            "symbol": symbol,
            "side": order.side,
            "order_type": order.order_type,
            "quantity": quantity,
            "filled_price": execution_price,
            "status": "FILLED",
            "realized_pnl": realized_pnl,
        }

        if (
            order.order_type == "LIMIT"
            and order.limit_price is not None
        ):

            result["limit_price"] = float(
                order.limit_price
            )

        elif (
            order.order_type == "STOP"
            and order.stop_price is not None
        ):

            result["stop_price"] = float(
                order.stop_price
            )

        results.append(
            result
        )

    # =====================================================
    # PORTFOLIO SNAPSHOT
    #
    # Only create a snapshot when an order was executed.
    # Reuse prices already fetched during this worker cycle.
    # =====================================================

    if results:

        positions = (
            db.query(Position)
            .filter(
                Position.user_id == user_id
            )
            .all()
        )

        portfolio_value = float(
            portfolio.balance
        )

        # Find symbols we do not already have prices for.
        snapshot_symbols = {
            position.symbol.upper().strip()
            for position in positions
            if position.symbol
        }

        missing_symbols = (
            snapshot_symbols
            - set(
                price_cache.keys()
            )
        )

        # Fetch only prices that were not already fetched
        # while checking pending orders.

        for symbol in missing_symbols:

            try:

                price = get_stock_price(
                    symbol
                )

                price_cache[symbol] = (
                    float(price)
                    if price is not None
                    else None
                )

            except Exception as e:

                print(
                    f"[ORDER WORKER] "
                    f"SNAPSHOT PRICE ERROR "
                    f"{symbol}: {e}"
                )

                price_cache[symbol] = None

        # Calculate portfolio value using cached prices.

        for position in positions:

            symbol = (
                position.symbol
                .upper()
                .strip()
            )

            price = price_cache.get(
                symbol
            )

            if price is not None:

                portfolio_value += (
                    float(position.quantity)
                    * price
                )

        snapshot = PortfolioSnapshot(
            user_id=user_id,
            total_value=portfolio_value,
        )

        db.add(
            snapshot
        )

    # =====================================================
    # COMMIT
    # =====================================================

    db.commit()

    return results