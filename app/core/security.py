from datetime import datetime, timedelta
import hashlib
import os

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv()


# =========================================================
# CONFIG
# =========================================================

SECRET_KEY = os.getenv("SECRET_KEY")

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        15,
    )
)

REFRESH_TOKEN_EXPIRE_DAYS = int(
    os.getenv(
        "REFRESH_TOKEN_EXPIRE_DAYS",
        7,
    )
)


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


# =========================================================
# PASSWORD HASHING
# =========================================================

def hash_password(password: str):

    return pwd_context.hash(
        password
    )


def verify_password(
    plain: str,
    hashed: str,
):

    return pwd_context.verify(
        plain,
        hashed,
    )


# =========================================================
# ACCESS TOKEN
# =========================================================

def create_access_token(
    data: dict,
):

    to_encode = data.copy()

    expire = (
        datetime.utcnow()
        + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    )

    to_encode.update({

        "exp": expire,

        "type": "access",

    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# =========================================================
# REFRESH TOKEN
# =========================================================

def create_refresh_token(
    data: dict,
):

    to_encode = data.copy()

    expire = (
        datetime.utcnow()
        + timedelta(
            days=REFRESH_TOKEN_EXPIRE_DAYS
        )
    )

    to_encode.update({

        "exp": expire,

        "type": "refresh",

    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# =========================================================
# REFRESH TOKEN HASHING
# =========================================================

def hash_refresh_token(
    token: str,
) -> str:

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


# =========================================================
# DECODE JWT
# =========================================================

def decode_token(
    token: str,
):

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[
                ALGORITHM
            ],
        )

        return payload

    except JWTError:

        return None