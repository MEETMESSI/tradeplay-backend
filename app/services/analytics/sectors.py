from sqlalchemy.orm import Session

from app.models.position import Position
from app.services.market_service import (
    get_stock_price,
    get_company_profile,
)


def get_sector_allocation(user_id: int, db: Session):

    positions = (
        db.query(Position)
        .filter(Position.user_id == user_id)
        .all()
    )

    if not positions:
        return []

    sectors = {}
    total_value = 0

    for position in positions:

        current_price = (
            get_stock_price(position.symbol)
            or position.avg_price
        )

        value = current_price * position.quantity

        profile = get_company_profile(position.symbol)

        sector = profile.get("sector", "Unknown")

        sectors[sector] = (
            sectors.get(sector, 0) + value
        )

        total_value += value

    results = []

    for sector, value in sectors.items():

        results.append({
            "sector": sector,
            "value": round(value, 2),
            "percentage": round(
                value / total_value * 100,
                2
            )
        })

    results.sort(
        key=lambda x: x["value"],
        reverse=True
    )

    return results