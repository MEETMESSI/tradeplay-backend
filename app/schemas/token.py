from pydantic import BaseModel


# -------------------------
# Refresh Token
# -------------------------

class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# -------------------------
# Forgot Password
# -------------------------

class ForgotPasswordRequest(BaseModel):
    email: str


# -------------------------
# Reset Password
# -------------------------

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str