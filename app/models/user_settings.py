from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
)

from sqlalchemy.orm import relationship

from app.db.database import Base


class UserSettings(Base):

    __tablename__ = "user_settings"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
        index=True,
    )

    # =====================================================
    # TRADING PREFERENCES
    # =====================================================

    default_order_type = Column(
        String,
        default="MARKET",
        nullable=False,
    )

    default_quantity = Column(
        Integer,
        default=1,
        nullable=False,
    )

    confirm_orders = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    # =====================================================
    # NOTIFICATIONS
    # =====================================================

    trading_notifications = Column(
        Boolean,
        default=True,
        nullable=False,
    )

    # =====================================================
    # DISPLAY
    # =====================================================

    theme = Column(
        String,
        default="dark",
        nullable=False,
    )

    # =====================================================
    # USER RELATIONSHIP
    # =====================================================

    user = relationship(
        "User",
        back_populates="settings",
    )