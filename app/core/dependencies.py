from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.core.security import decode_token


oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)


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
# CURRENT USER
# =========================================================

def get_current_user(
    token: str = Depends(
        oauth2_scheme
    ),
    db: Session = Depends(
        get_db
    ),
):

    payload = decode_token(
        token
    )


    if not payload:

        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )


    if payload.get(
        "type"
    ) != "access":

        raise HTTPException(
            status_code=401,
            detail="Invalid access token",
        )


    user_id = payload.get(
        "sub"
    )


    if user_id is None:

        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )


    user = (
        db.query(User)
        .filter(
            User.id == int(user_id)
        )
        .first()
    )


    if not user:

        raise HTTPException(
            status_code=401,
            detail="User not found",
        )


    return user


# =========================================================
# CURRENT SESSION
# =========================================================

def get_current_session(
    token: str = Depends(
        oauth2_scheme
    ),
    db: Session = Depends(
        get_db
    ),
):

    payload = decode_token(
        token
    )


    if not payload:

        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )


    if payload.get(
        "type"
    ) != "access":

        raise HTTPException(
            status_code=401,
            detail="Invalid access token",
        )


    user_id = payload.get(
        "sub"
    )

    session_id = payload.get(
        "sid"
    )


    if (
        user_id is None
        or session_id is None
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid session token",
        )


    session = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id
            == int(user_id),

            RefreshToken.token
            == session_id,

            RefreshToken.is_revoked
            == False,
        )
        .first()
    )


    if not session:

        raise HTTPException(
            status_code=401,
            detail="Session is no longer active",
        )


    if (
        session.expires_at
        < __import__(
            "datetime"
        ).datetime.utcnow()
    ):

        session.is_revoked = True

        db.commit()


        raise HTTPException(
            status_code=401,
            detail="Session has expired",
        )


    return session