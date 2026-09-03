from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.core.dependencies import get_current_user

from app.models.user import User
from app.models.user_settings import UserSettings


router = APIRouter()


# =========================================================
# DATABASE
# =========================================================

def get_db():

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()


# =========================================================
# GET SETTINGS
# =========================================================

@router.get("")
def get_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    settings = (
        db.query(UserSettings)
        .filter(
            UserSettings.user_id == current_user.id
        )
        .first()
    )


    # -----------------------------------------------------
    # CREATE DEFAULT SETTINGS
    # -----------------------------------------------------

    if not settings:

        settings = UserSettings(
            user_id=current_user.id,
            default_order_type="MARKET",
            default_quantity=1,
            confirm_orders=True,
            trading_notifications=True,
            theme="dark",
        )

        db.add(settings)
        db.commit()
        db.refresh(settings)


    return {
        "default_order_type": settings.default_order_type,
        "default_quantity": settings.default_quantity,
        "confirm_orders": settings.confirm_orders,
        "trading_notifications": settings.trading_notifications,
        "theme": settings.theme,
    }


# =========================================================
# UPDATE SETTINGS
# =========================================================

@router.put("")
def update_settings(
    data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    settings = (
        db.query(UserSettings)
        .filter(
            UserSettings.user_id == current_user.id
        )
        .first()
    )


    # -----------------------------------------------------
    # CREATE SETTINGS IF MISSING
    # -----------------------------------------------------

    if not settings:

        settings = UserSettings(
            user_id=current_user.id,
        )

        db.add(settings)


    # -----------------------------------------------------
    # DEFAULT ORDER TYPE
    # -----------------------------------------------------

    if "default_order_type" in data:

        allowed_order_types = {
            "MARKET",
            "LIMIT",
            "STOP",
        }

        order_type = str(
            data["default_order_type"]
        ).upper()


        if order_type in allowed_order_types:

            settings.default_order_type = (
                order_type
            )


    # -----------------------------------------------------
    # DEFAULT QUANTITY
    # -----------------------------------------------------

    if "default_quantity" in data:

        try:

            quantity = int(
                data["default_quantity"]
            )

            if quantity >= 1:

                settings.default_quantity = (
                    quantity
                )

        except (
            TypeError,
            ValueError,
        ):

            pass


    # -----------------------------------------------------
    # ORDER CONFIRMATION
    # -----------------------------------------------------

    if "confirm_orders" in data:

        settings.confirm_orders = bool(
            data["confirm_orders"]
        )


    # -----------------------------------------------------
    # NOTIFICATIONS
    # -----------------------------------------------------

    if "trading_notifications" in data:

        settings.trading_notifications = bool(
            data["trading_notifications"]
        )


    # -----------------------------------------------------
    # THEME
    # -----------------------------------------------------

    if "theme" in data:

        theme = str(
            data["theme"]
        ).lower()

        if theme in {
            "dark",
            "light",
        }:

            settings.theme = theme


    db.commit()
    db.refresh(settings)


    return {
        "message": "Settings updated successfully",

        "settings": {
            "default_order_type":
                settings.default_order_type,

            "default_quantity":
                settings.default_quantity,

            "confirm_orders":
                settings.confirm_orders,

            "trading_notifications":
                settings.trading_notifications,

            "theme":
                settings.theme,
        },
    }