from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.analytics_service import get_trade_stats

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/trade-stats")
def trade_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return get_trade_stats(
        current_user.id,
        db
    )