from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
)

from sqlalchemy.orm import relationship

from app.db.database import Base

from app.models.user_settings import UserSettings


class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    email = Column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    password = Column(
        String,
        nullable=False,
    )

    email_verified = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    verification_token_hash = Column(
        String,
        nullable=True,
    )

    verification_token_expires_at = Column(
        DateTime,
        nullable=True,
    )

    # =====================================================
    # SETTINGS
    # =====================================================

    settings = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )