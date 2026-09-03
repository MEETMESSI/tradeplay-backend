from sqlalchemy.orm import Session

from app.models.portfolio_snapshot import PortfolioSnapshot


def get_portfolio_history(user_id: int, db: Session):

    snapshots = (
        db.query(PortfolioSnapshot)
        .filter(
            PortfolioSnapshot.user_id == user_id
        )
        .order_by(
            PortfolioSnapshot.created_at.asc()
        )
        .all()
    )

    return [
        {
            "date": snapshot.created_at.isoformat(),
            "value": snapshot.total_value,
        }
        for snapshot in snapshots
    ]