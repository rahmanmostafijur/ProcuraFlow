PERMISSIONS: dict[str, str] = {
    "user:manage": "Manage users and roles",
    "supplier:write": "Create and edit suppliers",
    "product:write": "Create and edit products",
    "inventory:write": "Receive stock and adjust inventory",
    "po:create": "Create purchase orders in draft",
    "po:approve": "Submit and approve purchase orders",
    "po:transition": "Mark purchase orders ordered or cancelled",
    "audit:read": "View the audit log",
    "settings:manage": "Manage company settings and branding",
    "finance:manage": "Manage currencies, exchange rates and tax rates",
}

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": list(PERMISSIONS.keys()),
    "procurement_manager": [
        "supplier:write",
        "product:write",
        "po:create",
        "po:approve",
        "po:transition",
        "audit:read",
    ],
    "purchasing_officer": ["po:create", "po:transition"],
    "warehouse_manager": ["inventory:write"],
    "finance": ["finance:manage", "audit:read"],
    "viewer": [],
}

ROLE_DESCRIPTIONS: dict[str, str] = {
    "admin": "Full system access, including user and role management.",
    "procurement_manager": "Manages suppliers, products, and purchase order approvals.",
    "purchasing_officer": "Creates and progresses purchase orders.",
    "warehouse_manager": "Receives stock and manages inventory levels.",
    "finance": "Maintains currencies, exchange rates and tax rates, and reviews the audit log.",
    "viewer": "Read-only access across the platform.",
}
