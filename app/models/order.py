from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    ForeignKey,
    DateTime,
)

from datetime import datetime

from app.db.database import Base


class Order(Base):

    __tablename__ = "orders"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    symbol = Column(
        String,
        nullable=False,
        index=True,
    )

    quantity = Column(
        Float,
        nullable=False,
    )

    side = Column(
        String,
        nullable=False,
    )

    order_type = Column(
        String,
        nullable=False,
        default="MARKET",
    )

    limit_price = Column(
        Float,
        nullable=True,
    )

    stop_price = Column(
        Float,
        nullable=True,
    )

    status = Column(
        String,
        nullable=False,
        default="PENDING",
    )

    filled_price = Column(
        Float,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    filled_at = Column(
        DateTime,
        nullable=True,
    )

    cancelled_at = Column(
        DateTime,
        nullable=True,
    )