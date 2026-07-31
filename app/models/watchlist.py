from sqlalchemy import Column, Integer, String, ForeignKey
from app.db.database import Base

class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id")
    )

    symbol = Column(String)