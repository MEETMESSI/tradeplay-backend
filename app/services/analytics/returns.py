from sqlalchemy.orm import Session
from sqlalchemy import extract

from app.models.portfolio_snapshot import PortfolioSnapshot


def get_monthly_returns(user_id: int, db: Session):

    snapshots = (
        db.query(PortfolioSnapshot)
        .filter(
            PortfolioSnapshot.user_id == user_id
        )
        .order_by(PortfolioSnapshot.created_at.asc())
        .all()
    )

    if len(snapshots) < 2:
        return []

    months = {}

    for snapshot in snapshots:

        key = snapshot.created_at.strftime("%Y-%m")

        months[key] = snapshot.total_value

    monthly = []

    previous = None

    for month, value in months.items():

        if previous is None:
            previous = value
            continue

        pct = (
            (value - previous)
            / previous
        ) * 100

        monthly.append({
            "month": month,
            "return": round(pct, 2)
        })

        previous = value

    return monthly