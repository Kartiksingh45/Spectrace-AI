"""Transactional email via Resend's HTTP API (free tier, no card required) - no SDK dependency,
just a plain httpx POST, matching how embeddings.py/github_import.py call other external APIs.
"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_API_URL = "https://api.resend.com/emails"


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    """Best-effort: a delivery failure is logged, never raised - forgot-password must still return
    its content-free 204 either way, so a Resend outage can't be used to probe which emails are
    registered.
    """
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not set - skipping password reset email to %s", to_email)
        return

    try:
        httpx.post(
            _API_URL,
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.resend_from_email,
                "to": [to_email],
                "subject": "Reset your Spectrace AI password",
                "html": (
                    f"<p>Click the link below to reset your Spectrace AI password. "
                    f"This link expires in {settings.password_reset_token_expire_minutes} minutes.</p>"
                    f'<p><a href="{reset_url}">{reset_url}</a></p>'
                    f"<p>If you didn't request this, you can safely ignore this email.</p>"
                ),
            },
            timeout=10,
        ).raise_for_status()
    except httpx.HTTPError:
        logger.exception("Failed to send password reset email to %s", to_email)
