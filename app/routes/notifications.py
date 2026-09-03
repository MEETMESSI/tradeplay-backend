from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import SessionLocal
from app.models.notification import Notification
from app.models.user import User


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
# GET NOTIFICATIONS
# =========================================================

@router.get("/")
def get_notifications(

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),

):

    notifications = (

        db.query(Notification)

        .filter(
            Notification.user_id
            == current_user.id
        )

        .order_by(
            Notification.created_at.desc()
        )

        .limit(50)

        .all()

    )


    unread_count = (

        db.query(Notification)

        .filter(
            Notification.user_id
            == current_user.id,

            Notification.is_read
            == False,
        )

        .count()

    )


    return {

        "notifications": [

            {

                "id": notification.id,

                "title":
                    notification.title,

                "message":
                    notification.message,

                "notification_type":
                    notification.notification_type,

                "is_read":
                    notification.is_read,

                "created_at":
                    notification.created_at,

            }

            for notification
            in notifications

        ],

        "unread_count":
            unread_count,

    }


# =========================================================
# MARK ONE NOTIFICATION AS READ
# =========================================================

@router.put("/{notification_id}/read")
def mark_notification_read(

    notification_id: int,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),

):

    notification = (

        db.query(Notification)

        .filter(
            Notification.id
            == notification_id,

            Notification.user_id
            == current_user.id,
        )

        .first()

    )


    if not notification:

        raise HTTPException(
            status_code=404,
            detail="Notification not found",
        )


    notification.is_read = True

    db.commit()

    return {

        "message":
            "Notification marked as read"

    }


# =========================================================
# MARK ALL NOTIFICATIONS AS READ
# =========================================================

@router.put("/read-all")
def mark_all_notifications_read(

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),

):

    (

        db.query(Notification)

        .filter(
            Notification.user_id
            == current_user.id,

            Notification.is_read
            == False,
        )

        .update(
            {
                Notification.is_read:
                    True
            }
        )

    )


    db.commit()


    return {

        "message":
            "All notifications marked as read"

    }