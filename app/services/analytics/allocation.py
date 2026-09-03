from sqlalchemy.orm import Session

from app.models.position import Position
from app.services.market_service import get_stock_price


def get_portfolio_allocation(
    user_id: int,
    db: Session,
):
    """
    Return current portfolio allocation by position.

    Each position contains:
        - symbol
        - quantity
        - market_value
        - allocation_percent
    """

    positions = (
        db.query(Position)
        .filter(
            Position.user_id == user_id,
            Position.quantity > 0,
        )
        .all()
    )

    if not positions:
        return []

    allocation_data = []

    total_market_value = 0.0

    # =====================================================
    # CALCULATE MARKET VALUES
    # =====================================================

    for position in positions:

        symbol = position.symbol.upper()

        current_price = get_stock_price(symbol)

        if current_price is None:
            continue

        market_value = (
            float(position.quantity)
            * float(current_price)
        )

        total_market_value += market_value

        allocation_data.append({
            "symbol": symbol,
            "quantity": float(
                position.quantity
            ),
            "price": float(
                current_price
            ),
            "market_value": market_value,
        })

    # =====================================================
    # CALCULATE ALLOCATION %
    # =====================================================

    if total_market_value <= 0:
        return []

    for item in allocation_data:

        item["allocation_percent"] = (
            item["market_value"]
            / total_market_value
        ) * 100

    # =====================================================
    # SORT LARGEST → SMALLEST
    # =====================================================

    allocation_data.sort(
        key=lambda item:
        item["market_value"],
        reverse=True,
    )

    return allocation_data