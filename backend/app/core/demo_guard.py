"""Demo mode: what a visitor of the public demo may not do, in one list.

Everything here is inert unless ``DEMO_MODE=true``. The guard is a single application-wide dependency
(``app.main`` registers it), so a new endpoint is covered by adding one rule below, not by touching its router.

Blocked: user deletion and deactivation, role changes, any password change, GDPR anonymisation, deleting exchange
rates and changing the company settings that would break the seeded data (currency, fiscal year, time zone,
numbering, matching rules, payer bank account). Exports, reads and ordinary work stay open.
"""

import re
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status

from app.core.config import get_settings

API_PREFIX = "/api/v1"
DEMO_EMAIL_DOMAIN = "demo.example.com"
DEMO_BLOCKED_MESSAGE = "This action is turned off in the demo"

Body = dict[str, Any]
BodyTest = Callable[[Body], bool]

# True while the demo seed runs in this process: it uses the same API as a visitor but must be allowed through.
# A context variable cannot be set by a request, unlike a header.
_seeding: ContextVar[bool] = ContextVar("demo_seeding", default=False)


@contextmanager
def seeding_allowed() -> Iterator[None]:
    token = _seeding.set(True)
    try:
        yield
    finally:
        _seeding.reset(token)


def is_demo_email(email: str) -> bool:
    return email.lower().endswith(f"@{DEMO_EMAIL_DOMAIN}")


@dataclass(frozen=True)
class DemoRule:
    method: str
    path: re.Pattern[str]
    reason: str
    # Inspects the JSON body when the path alone is not enough (None: the path decides).
    when_body: BodyTest | None = None


def _compiled(pattern: str) -> re.Pattern[str]:
    return re.compile(f"^{pattern}/?$")


def _deactivates(body: Body) -> bool:
    return body.get("is_active") is False


def _changes_role_or_password(body: Body) -> bool:
    return "role_id" in body or bool(body.get("password"))


def _touches_user_protection(body: Body) -> bool:
    return _deactivates(body) or _changes_role_or_password(body)


# Settings the seeded data depends on; branding and contact details stay editable.
PROTECTED_SETTINGS = frozenset(
    {
        "base_currency_code",
        "fiscal_year_start_month",
        "timezone",
        "po_number_prefix",
        "invoice_tolerance_percent",
        "invoice_matching",
        "budget_block_over_budget",
        "budget_warn_percent",
        "payer_iban",
        "payer_bic",
        "payer_routing_number",
        "payer_account_number",
        "ach_company_id",
    }
)


def _touches_protected_setting(body: Body) -> bool:
    return not PROTECTED_SETTINGS.isdisjoint(body)


DEMO_RULES: tuple[DemoRule, ...] = (
    # A visitor who is the demo admin could otherwise create an admin with a password of their choosing; such an
    # account is not a demo account, so it would outlive the demo being switched off. Invitations stay open: they
    # carry no password and the invitation email is only logged in the demo.
    DemoRule("POST", _compiled(r"/users"), "New accounts cannot be created"),
    DemoRule("DELETE", _compiled(r"/users/\d+"), "Users cannot be deleted"),
    DemoRule(
        "PATCH",
        _compiled(r"/users/\d+"),
        "Users cannot be deactivated and roles and passwords stay as they are",
        _touches_user_protection,
    ),
    DemoRule("POST", _compiled(r"/auth/change-password"), "Demo passwords cannot be changed"),
    DemoRule("POST", _compiled(r"/auth/password-reset/confirm"), "Demo passwords cannot be changed"),
    DemoRule("POST", _compiled(r"/gdpr/users/\d+/anonymise"), "Personal data cannot be anonymised"),
    DemoRule("POST", _compiled(r"/gdpr/suppliers/\d+/contact/anonymise"), "Personal data cannot be anonymised"),
    DemoRule("PATCH", _compiled(r"/company-settings"), "These company settings stay fixed", _touches_protected_setting),
    DemoRule("DELETE", _compiled(r"/exchange-rates/\d+"), "Exchange rates cannot be deleted"),
)


def find_blocking_rule(method: str, path: str, body: Body | None) -> DemoRule | None:
    """The first rule the request breaks, or None. ``path`` may carry the API prefix."""
    relative = path.removeprefix(API_PREFIX)
    for rule in DEMO_RULES:
        if rule.method != method or not rule.path.match(relative):
            continue
        if rule.when_body is None or (body is not None and rule.when_body(body)):
            return rule
    return None


async def _json_body(request: Request) -> Body | None:
    try:
        body = await request.json()
    except ValueError:
        return None
    return body if isinstance(body, dict) else None


async def demo_guard(request: Request) -> None:
    """Application-wide dependency: refuse the requests in DEMO_RULES while the demo is on."""
    if not get_settings().demo_mode or _seeding.get() or request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    needs_body = any(rule.method == request.method and rule.when_body for rule in DEMO_RULES)
    body = await _json_body(request) if needs_body else None
    rule = find_blocking_rule(request.method, request.url.path, body)
    if rule is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{DEMO_BLOCKED_MESSAGE}: {rule.reason}.")


async def require_demo_mode() -> None:
    """Dependency for the demo-only routes: outside the demo they do not exist."""
    if not get_settings().demo_mode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
