from typing import Any

from app.core.config import Settings

REFRESH_COOKIE_NAME = "refresh_token"
# Scoped to the auth routes so the browser never attaches the refresh token to ordinary API calls.
REFRESH_COOKIE_PATH = "/api/v1/auth"
SECONDS_PER_DAY = 24 * 60 * 60


def refresh_cookie_options(settings: Settings) -> dict[str, Any]:
    """Attributes for the refresh-token cookie.

    HttpOnly keeps the token out of reach of page scripts (XSS). SameSite=Lax means browsers
    omit it on cross-site POSTs, which is what makes /auth/refresh safe from CSRF. The Vercel
    proxy keeps the API same-origin, so Lax is enough and the cookie stays first-party.
    """
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": not settings.is_local,
        "path": REFRESH_COOKIE_PATH,
        "max_age": settings.refresh_token_expire_days * SECONDS_PER_DAY,
    }
