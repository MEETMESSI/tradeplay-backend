import os

import resend
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY")

EMAIL_FROM = os.getenv(
    "EMAIL_FROM",
    "onboarding@resend.dev",
)

BACKEND_URL = os.getenv(
    "BACKEND_URL",
    "http://127.0.0.1:8000",
)

FRONTEND_URL = os.getenv(
    "FRONTEND_URL",
    "http://localhost:5173",
)

if not RESEND_API_KEY:
    raise RuntimeError(
        "RESEND_API_KEY is not configured"
    )

resend.api_key = RESEND_API_KEY


# =========================================================
# EMAIL VERIFICATION
# =========================================================

async def send_verification_email(
    email: str,
    verification_token: str,
):
    verification_url = (
        f"{BACKEND_URL}/auth/verify-email"
        f"?token={verification_token}"
    )

    params = {
        "from": EMAIL_FROM,
        "to": [email],
        "subject": "Verify your Tradeplay account",
        "html": f"""
        <html>
            <body>
                <h2>Welcome to Tradeplay</h2>

                <p>
                    Thanks for creating your Tradeplay account.
                </p>

                <p>
                    Click below to verify your email address:
                </p>

                <p>
                    <a href="{verification_url}">
                        Verify Email
                    </a>
                </p>

                <p>
                    This link expires in 30 minutes.
                </p>

                <p>
                    If you did not create this account,
                    you can safely ignore this email.
                </p>
            </body>
        </html>
        """,
    }

    return await resend.Emails.send_async(params)


# =========================================================
# PASSWORD RESET
# =========================================================

async def send_password_reset_email(
    email: str,
    reset_token: str,
):
    reset_url = (
        f"{FRONTEND_URL}/reset-password"
        f"?token={reset_token}"
    )

    params = {
        "from": EMAIL_FROM,
        "to": [email],
        "subject": "Reset your Tradeplay password",
        "html": f"""
        <html>
            <body>
                <h2>Reset your Tradeplay password</h2>

                <p>
                    We received a request to reset your password.
                </p>

                <p>
                    Click below to choose a new password:
                </p>

                <p>
                    <a href="{reset_url}">
                        Reset Password
                    </a>
                </p>

                <p>
                    This link expires in 30 minutes.
                </p>

                <p>
                    If you did not request a password reset,
                    you can safely ignore this email.
                </p>
            </body>
        </html>
        """,
    }

    return await resend.Emails.send_async(params)