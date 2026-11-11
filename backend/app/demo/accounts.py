"""The demo sign-in accounts: one per role, two finance people (a payment run needs a second releaser) and the
portal accounts of the two invited suppliers.

Credentials: every demo account shares one password. It is ``DEMO_PASSWORD`` when set, otherwise derived from
``JWT_SECRET_KEY``, so a deployment has its own and no password is written in the source. The one-click demo login
never needs it; ``python -m app.cli.demo_reset`` prints it for people who want to type it. Demo accounts only
sign in while ``DEMO_MODE`` is on (see ``app.core.demo_guard``).
"""

import base64
import hashlib
import hmac
from dataclasses import dataclass

from app.core.config import Settings
from app.core.demo_guard import DEMO_EMAIL_DOMAIN

PASSWORD_LENGTH = 20
PASSWORD_CONTEXT = b"procuraflow-demo-password-v1"


@dataclass(frozen=True)
class DemoAccount:
    key: str
    role_name: str
    full_name: str
    description: str
    # Set for the portal accounts: the fictional supplier (by name) the account belongs to.
    supplier_name: str | None = None

    @property
    def email(self) -> str:
        return f"{self.key}@{DEMO_EMAIL_DOMAIN}"

    @property
    def is_portal(self) -> bool:
        return self.supplier_name is not None


# Supplier names are the fictional ones defined in app.demo.catalog.
DEMO_ACCOUNTS: tuple[DemoAccount, ...] = (
    DemoAccount("admin", "admin", "Avery Quinn", "Everything, including users, roles and settings"),
    DemoAccount(
        "procurement_manager",
        "procurement_manager",
        "Priya Raman",
        "Suppliers, products, purchase order approvals and amendments",
    ),
    DemoAccount("purchasing_officer", "purchasing_officer", "Tom Becker", "Raises and progresses purchase orders"),
    DemoAccount("warehouse_manager", "warehouse_manager", "Lena Fischer", "Receives goods, returns and stock"),
    DemoAccount("finance", "finance", "Grace Okafor", "Invoices, payments, budgets and approval rules"),
    DemoAccount("finance_approver", "finance", "Hugo Martin", "Second finance user: releases payment runs"),
    DemoAccount(
        "department_manager", "department_manager", "Marcus Webb", "Approves team requests, covers for Priya Raman"
    ),
    DemoAccount("employee", "employee", "Jamie Lopez", "Raises purchase requests"),
    DemoAccount("viewer", "viewer", "Riley Chen", "Read-only access"),
    DemoAccount(
        "supplier",
        "supplier",
        "Casey Morgan",
        "Supplier portal of Prairie Office Supply Co.",
        supplier_name="Prairie Office Supply Co.",
    ),
    DemoAccount(
        "supplier_eu",
        "supplier",
        "Katrin Vogel",
        "Supplier portal of Rheinwerk Elektronik GmbH",
        supplier_name="Rheinwerk Elektronik GmbH",
    ),
)
ACCOUNTS_BY_KEY: dict[str, DemoAccount] = {account.key: account for account in DEMO_ACCOUNTS}


def demo_password(settings: Settings) -> str:
    """The shared demo password: configured, or derived from the JWT secret (stable, unique per deployment)."""
    if settings.demo_password:
        return settings.demo_password
    digest = hmac.new(settings.jwt_secret_key.encode(), PASSWORD_CONTEXT, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode()[:PASSWORD_LENGTH]
