from sqlalchemy import Column, Integer, Float, String, ForeignKey, DateTime
from datetime import datetime
from app.db.database import Base

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    symbol = Column(String)
    quantity = Column(Float)

    price = Column(Float)
    side = Column(String)

    avg_cost = Column(Float, nullable=True)
    realized_pnl = Column(Float, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)