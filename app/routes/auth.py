from datetime import datetime, timedelta
import hashlib
import secrets

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from fastapi.security import (
    OAuth2PasswordRequestForm,
)

from sqlalchemy.orm import Session

from app.db.database import SessionLocal

from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.password_reset_token import PasswordResetToken

from app.schemas.user import (
    UserCreate,
    ChangePasswordRequest,
)

from app.schemas.token import (
    RefreshTokenRequest,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)

from app.core.dependencies import (
    get_current_user,
    get_current_session,
)

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_refresh_token,
    REFRESH_TOKEN_EXPIRE_DAYS,
)

from app.core.audit import (
    create_audit_log,
)

from app.core.email import (
    send_verification_email,
    send_password_reset_email,
)


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
# CLIENT IP
# =========================================================

def get_client_ip(request: Request):

    if request.client:
        return request.client.host

    return None


# =========================================================
# DEVICE NAME
# =========================================================

def get_device_name(request: Request):

    user_agent = (
        request.headers.get(
            "user-agent",
            "",
        )
        .lower()
    )

    # -----------------------------------------------------
    # BROWSER
    # -----------------------------------------------------

    if "edg" in user_agent:
        browser = "Microsoft Edge"

    elif "chrome" in user_agent:
        browser = "Google Chrome"

    elif "firefox" in user_agent:
        browser = "Mozilla Firefox"

    elif "safari" in user_agent:
        browser = "Safari"

    else:
        browser = "Unknown Browser"


    # -----------------------------------------------------
    # OPERATING SYSTEM
    # -----------------------------------------------------

    if "windows" in user_agent:
        os_name = "Windows"

    elif "macintosh" in user_agent:
        os_name = "macOS"

    elif "iphone" in user_agent:
        os_name = "iPhone"

    elif "ipad" in user_agent:
        os_name = "iPad"

    elif "android" in user_agent:
        os_name = "Android"

    elif "linux" in user_agent:
        os_name = "Linux"

    else:
        os_name = "Unknown OS"


    return f"{browser} • {os_name}"


# =========================================================
# SIGNUP
# =========================================================

@router.post("/signup")
async def signup(
    user: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):

    existing_user = (
        db.query(User)
        .filter(
            User.email == user.email
        )
        .first()
    )

    if existing_user:

        create_audit_log(
            db=db,
            action="SIGNUP_FAILED",
            ip_address=get_client_ip(request),
            details="Email already registered",
        )

        db.commit()

        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )


    verification_token = (
        secrets.token_urlsafe(32)
    )

    verification_token_hash = (
        hashlib.sha256(
            verification_token.encode("utf-8")
        ).hexdigest()
    )

    verification_expires = (
        datetime.utcnow()
        + timedelta(minutes=30)
    )


    new_user = User(
        email=user.email,
        password=hash_password(
            user.password
        ),
        email_verified=False,
        verification_token_hash=(
            verification_token_hash
        ),
        verification_token_expires_at=(
            verification_expires
        ),
    )


    db.add(new_user)

    db.flush()


    create_audit_log(
        db=db,
        action="SIGNUP_SUCCESS",
        user_id=new_user.id,
        ip_address=get_client_ip(request),
    )


    db.commit()


    try:

        await send_verification_email(
            email=new_user.email,
            verification_token=verification_token,
        )

    except Exception as e:

        print(
            "Verification email failed:",
            str(e),
        )

        raise HTTPException(
            status_code=500,
            detail=(
                "Account created but verification "
                "email could not be sent"
            ),
        )


    return {
        "message": (
            "Account created successfully. "
            "Please check your email to verify your account."
        )
    }


# =========================================================
# VERIFY EMAIL
# =========================================================

@router.get("/verify-email")
def verify_email(
    token: str,
    db: Session = Depends(get_db),
):

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


    user = (
        db.query(User)
        .filter(
            User.verification_token_hash
            == token_hash
        )
        .first()
    )


    if not user:

        raise HTTPException(
            status_code=400,
            detail="Invalid verification token",
        )


    if user.email_verified:

        return {
            "message": "Email already verified"
        }


    if (
        not user.verification_token_expires_at
        or
        user.verification_token_expires_at
        < datetime.utcnow()
    ):

        raise HTTPException(
            status_code=400,
            detail="Verification token expired",
        )


    user.email_verified = True

    user.verification_token_hash = None

    user.verification_token_expires_at = None


    create_audit_log(
        db=db,
        action="EMAIL_VERIFIED",
        user_id=user.id,
    )


    db.commit()


    return {
        "message":
            "Email verified successfully"
    }


# =========================================================
# FORGOT PASSWORD
# =========================================================

@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):

    user = (
        db.query(User)
        .filter(
            User.email == request.email
        )
        .first()
    )


    if not user:

        return {
            "message": (
                "If an account with that email exists, "
                "a password reset link has been sent."
            )
        }


    db.query(
        PasswordResetToken
    ).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.is_used == False,
    ).update(
        {
            PasswordResetToken.is_used: True
        },
        synchronize_session=False,
    )


    reset_token = (
        secrets.token_urlsafe(32)
    )


    reset_token_hash = hashlib.sha256(
        reset_token.encode("utf-8")
    ).hexdigest()


    reset_expires = (
        datetime.utcnow()
        + timedelta(minutes=30)
    )


    db_reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=reset_token_hash,
        expires_at=reset_expires,
        is_used=False,
    )


    db.add(db_reset_token)


    create_audit_log(
        db=db,
        action="PASSWORD_RESET_REQUESTED",
        user_id=user.id,
        ip_address=get_client_ip(http_request),
    )


    db.commit()


    try:

        await send_password_reset_email(
            email=user.email,
            reset_token=reset_token,
        )

    except Exception as e:

        print(
            "Password reset email failed:",
            str(e),
        )


    return {
        "message": (
            "If an account with that email exists, "
            "a password reset link has been sent."
        )
    }


# =========================================================
# RESET PASSWORD
# =========================================================

@router.post("/reset-password")
def reset_password(
    request: ResetPasswordRequest,
    http_request: Request,
    db: Session = Depends(get_db),
):

    token_hash = hashlib.sha256(
        request.token.encode("utf-8")
    ).hexdigest()


    db_reset_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash
            == token_hash,

            PasswordResetToken.is_used
            == False,
        )
        .first()
    )


    if not db_reset_token:

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token",
        )


    if (
        db_reset_token.expires_at
        < datetime.utcnow()
    ):

        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token",
        )


    user = (
        db.query(User)
        .filter(
            User.id
            == db_reset_token.user_id
        )
        .first()
    )


    if not user:

        raise HTTPException(
            status_code=400,
            detail="Invalid reset request",
        )


    if len(request.new_password) < 8:

        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be at least "
                "8 characters long"
            ),
        )


    user.password = hash_password(
        request.new_password
    )


    db_reset_token.is_used = True


    db.query(
        RefreshToken
    ).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked == False,
    ).update(
        {
            RefreshToken.is_revoked: True
        },
        synchronize_session=False,
    )


    create_audit_log(
        db=db,
        action="PASSWORD_RESET_SUCCESS",
        user_id=user.id,
        ip_address=get_client_ip(http_request),
    )


    db.commit()


    return {
        "message": (
            "Password reset successfully. "
            "Please log in again."
        )
    }


# =========================================================
# LOGIN
# =========================================================

@router.post("/login")
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):

    db_user = (
        db.query(User)
        .filter(
            User.email == form_data.username
        )
        .first()
    )


    if not db_user:

        create_audit_log(
            db=db,
            action="LOGIN_FAILED",
            ip_address=get_client_ip(request),
            details="Invalid credentials",
        )

        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )


    if not verify_password(
        form_data.password,
        db_user.password,
    ):

        create_audit_log(
            db=db,
            action="LOGIN_FAILED",
            user_id=db_user.id,
            ip_address=get_client_ip(request),
            details="Invalid credentials",
        )

        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )


    if not db_user.email_verified:

        create_audit_log(
            db=db,
            action="LOGIN_FAILED",
            user_id=db_user.id,
            ip_address=get_client_ip(request),
            details="Email not verified",
        )

        db.commit()

        raise HTTPException(
            status_code=403,
            detail=(
                "Please verify your email "
                "before logging in."
            ),
        )


    # -----------------------------------------------------
    # DEVICE
    # -----------------------------------------------------

    device_name = get_device_name(
        request
    )


    # -----------------------------------------------------
    # REFRESH TOKEN
    # -----------------------------------------------------

    refresh_token = create_refresh_token(
        {
            "sub":
                str(db_user.id)
        }
    )


    refresh_token_hash = (
        hash_refresh_token(
            refresh_token
        )
    )


    # -----------------------------------------------------
    # ACCESS TOKEN
    #
    # sid identifies the refresh-token session.
    # -----------------------------------------------------

    access_token = create_access_token(
        {
            "sub":
                str(db_user.id),

            "sid":
                refresh_token_hash,
        }
    )


    # -----------------------------------------------------
    # STORE SESSION
    # -----------------------------------------------------

    db_refresh = RefreshToken(
        user_id=db_user.id,

        token=refresh_token_hash,

        device_name=device_name,

        expires_at=(
            datetime.utcnow()
            + timedelta(
                days=REFRESH_TOKEN_EXPIRE_DAYS
            )
        ),
    )


    db.add(db_refresh)


    create_audit_log(
        db=db,
        action="LOGIN_SUCCESS",
        user_id=db_user.id,
        ip_address=get_client_ip(request),
        details=device_name,
    )


    db.commit()


    return {
        "access_token":
            access_token,

        "refresh_token":
            refresh_token,

        "token_type":
            "bearer",
    }


# =========================================================
# REFRESH
# =========================================================

@router.post(
    "/refresh",
    response_model=TokenResponse,
)
def refresh_token(
    request: Request,
    token_request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):

    payload = decode_token(
        token_request.refresh_token
    )


    if not payload:

        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )


    if payload.get("type") != "refresh":

        raise HTTPException(
            status_code=401,
            detail="Invalid token type",
        )


    user_id = payload.get("sub")


    if not user_id:

        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )


    refresh_token_hash = (
        hash_refresh_token(
            token_request.refresh_token
        )
    )


    db_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token
            == refresh_token_hash,

            RefreshToken.is_revoked
            == False,
        )
        .first()
    )


    if not db_token:

        raise HTTPException(
            status_code=401,
            detail="Refresh token not found",
        )


    if (
        db_token.expires_at
        < datetime.utcnow()
    ):

        db_token.is_revoked = True

        db.commit()

        raise HTTPException(
            status_code=401,
            detail="Refresh token expired",
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


    new_access_token = create_access_token(
        {
            "sub":
                str(user.id),

            "sid":
                refresh_token_hash,
        }
    )


    create_audit_log(
        db=db,
        action="TOKEN_REFRESH",
        user_id=user.id,
        ip_address=get_client_ip(request),
    )


    db.commit()


    return {
        "access_token":
            new_access_token,

        "token_type":
            "bearer",
    }


# =========================================================
# LOGOUT
# =========================================================

@router.post("/logout")
def logout(
    request: Request,
    token_request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):

    refresh_token_hash = (
        hash_refresh_token(
            token_request.refresh_token
        )
    )


    db_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token
            == refresh_token_hash,

            RefreshToken.is_revoked
            == False,
        )
        .first()
    )


    if not db_token:

        raise HTTPException(
            status_code=401,
            detail="Refresh token not found",
        )


    db_token.is_revoked = True


    create_audit_log(
        db=db,
        action="LOGOUT",
        user_id=db_token.user_id,
        ip_address=get_client_ip(request),
    )


    db.commit()


    return {
        "message":
            "Logged out successfully"
    }


# =========================================================
# LOGOUT ALL
# =========================================================

@router.post("/logout-all")
def logout_all(
    request: Request,
    token_request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):

    payload = decode_token(
        token_request.refresh_token
    )


    if not payload:

        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )


    if payload.get("type") != "refresh":

        raise HTTPException(
            status_code=401,
            detail="Invalid token type",
        )


    user_id = payload.get("sub")


    if not user_id:

        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token",
        )


    refresh_token_hash = (
        hash_refresh_token(
            token_request.refresh_token
        )
    )


    current_token = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.token
            == refresh_token_hash,

            RefreshToken.is_revoked
            == False,
        )
        .first()
    )


    if not current_token:

        raise HTTPException(
            status_code=401,
            detail="Refresh token not found",
        )


    db.query(
        RefreshToken
    ).filter(
        RefreshToken.user_id
        == int(user_id),

        RefreshToken.is_revoked
        == False,
    ).update(
        {
            RefreshToken.is_revoked:
                True
        },
        synchronize_session=False,
    )


    create_audit_log(
        db=db,
        action="LOGOUT_ALL",
        user_id=int(user_id),
        ip_address=get_client_ip(request),
    )


    db.commit()


    return {
        "message":
            "Logged out from all devices"
    }


# =========================================================
# ACTIVE SESSIONS
# =========================================================

@router.get("/sessions")
def get_sessions(
    current_user: User = Depends(
        get_current_user
    ),

    current_session: RefreshToken = Depends(
        get_current_session
    ),

    db: Session = Depends(
        get_db
    ),
):

    sessions = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.user_id
            == current_user.id,

            RefreshToken.is_revoked
            == False,

            RefreshToken.expires_at
            > datetime.utcnow(),
        )
        .order_by(
            RefreshToken.created_at.desc()
        )
        .all()
    )


    return [

        {
            "id":
                session.id,

            "device_name":
                session.device_name
                or "Unknown Device",

            "created_at":
                session.created_at,

            "expires_at":
                session.expires_at,

            "is_current":
                session.id
                == current_session.id,
        }

        for session in sessions

    ]


# =========================================================
# REVOKE ONE SESSION
# =========================================================

@router.delete(
    "/sessions/{session_id}"
)
def revoke_session(
    session_id: int,
    request: Request,

    current_user: User = Depends(
        get_current_user
    ),

    current_session: RefreshToken = Depends(
        get_current_session
    ),

    db: Session = Depends(
        get_db
    ),
):

    # -----------------------------------------------------
    # PREVENT REVOKING CURRENT SESSION
    # -----------------------------------------------------

    if session_id == current_session.id:

        raise HTTPException(
            status_code=400,
            detail=(
                "You cannot revoke your current session. "
                "Use Logout instead."
            ),
        )


    session = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.id
            == session_id,

            RefreshToken.user_id
            == current_user.id,

            RefreshToken.is_revoked
            == False,
        )
        .first()
    )


    if not session:

        raise HTTPException(
            status_code=404,
            detail="Session not found",
        )


    session.is_revoked = True


    create_audit_log(
        db=db,
        action="SESSION_REVOKED",
        user_id=current_user.id,
        ip_address=get_client_ip(request),
        details=(
            f"Session {session_id} revoked"
        ),
    )


    db.commit()


    return {
        "message":
            "Session revoked successfully"
    }


# =========================================================
# CHANGE PASSWORD
# =========================================================

@router.post("/change-password")
def change_password(
    password_request: ChangePasswordRequest,

    request: Request,

    current_user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    ),
):

    # -----------------------------------------------------
    # CURRENT PASSWORD
    # -----------------------------------------------------

    if not verify_password(
        password_request.current_password,
        current_user.password,
    ):

        create_audit_log(
            db=db,
            action="PASSWORD_CHANGE_FAILED",
            user_id=current_user.id,
            ip_address=get_client_ip(request),
            details="Current password incorrect",
        )

        db.commit()

        raise HTTPException(
            status_code=400,
            detail=(
                "Current password is incorrect"
            ),
        )


    # -----------------------------------------------------
    # PASSWORD LENGTH
    # -----------------------------------------------------

    if len(
        password_request.new_password
    ) < 8:

        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be at least "
                "8 characters long"
            ),
        )


    # -----------------------------------------------------
    # CONFIRM PASSWORD
    # -----------------------------------------------------

    if (
        password_request.new_password
        !=
        password_request.confirm_password
    ):

        raise HTTPException(
            status_code=400,
            detail="New passwords do not match",
        )


    # -----------------------------------------------------
    # DIFFERENT PASSWORD
    # -----------------------------------------------------

    if verify_password(
        password_request.new_password,
        current_user.password,
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "New password must be different "
                "from your current password"
            ),
        )


    # -----------------------------------------------------
    # UPDATE
    # -----------------------------------------------------

    current_user.password = hash_password(
        password_request.new_password
    )


    # -----------------------------------------------------
    # REVOKE ALL SESSIONS
    # -----------------------------------------------------

    db.query(
        RefreshToken
    ).filter(
        RefreshToken.user_id
        == current_user.id,

        RefreshToken.is_revoked
        == False,
    ).update(
        {
            RefreshToken.is_revoked:
                True
        },
        synchronize_session=False,
    )


    create_audit_log(
        db=db,
        action="PASSWORD_CHANGE_SUCCESS",
        user_id=current_user.id,
        ip_address=get_client_ip(request),
    )


    db.commit()


    return {
        "message": (
            "Password changed successfully. "
            "Please log in again."
        )
    }


# =========================================================
# ACCOUNT INFORMATION
# =========================================================

@router.get("/me")
def get_account_info(
    current_user: User = Depends(
        get_current_user
    ),
):

    return {
        "id":
            current_user.id,

        "email":
            current_user.email,

        "email_verified":
            current_user.email_verified,
    }