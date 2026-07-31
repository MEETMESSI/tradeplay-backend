from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from datetime import datetime

from app.db.database import Base

class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    total_value = Column(Float)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )