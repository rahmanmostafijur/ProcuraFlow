from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.demo_guard import demo_guard
from app.core.proxy import TrustedProxyMiddleware
from app.routers import (
    account,
    approval_admin,
    approvals,
    attachments,
    audit,
    auth,
    budgets,
    catalog,
    categories,
    company_settings,
    currencies,
    dashboard,
    deliveries,
    demo_auth,
    email_templates,
    exports,
    gdpr,
    health,
    inventory,
    notifications,
    payment_files,
    payment_runs,
    po_amendments,
    portal,
    products,
    purchase_orders,
    purchase_requests,
    reports,
    roles,
    search,
    supplier_bank,
    supplier_documents,
    supplier_invoices,
    supplier_portal_admin,
    supplier_returns,
    suppliers,
    tax_rates,
    users,
)

settings = get_settings()

# One application-wide guard for the public demo (a no-op unless DEMO_MODE is on); see app/core/demo_guard.py.
app = FastAPI(title="ProcuraFlow API", version="1.0.0", dependencies=[Depends(demo_guard)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last so it is the outermost layer and resolves the client address before anything else runs.
app.add_middleware(TrustedProxyMiddleware, hops=lambda: settings.trusted_proxy_hops)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred"})


# Bare path for the hosting platform's health probe; /api/health and /api/ready are the
# same-origin routes the frontend reaches through its /api proxy.
@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(health.router, prefix="/api")

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(demo_auth.router, prefix=API_PREFIX)
app.include_router(account.router, prefix=API_PREFIX)
app.include_router(email_templates.router, prefix=API_PREFIX)
app.include_router(notifications.router, prefix=API_PREFIX)
app.include_router(roles.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)
app.include_router(suppliers.router, prefix=API_PREFIX)
app.include_router(supplier_documents.router, prefix=API_PREFIX)
app.include_router(supplier_bank.router, prefix=API_PREFIX)
app.include_router(supplier_portal_admin.router, prefix=API_PREFIX)
app.include_router(portal.router, prefix=API_PREFIX)
app.include_router(categories.router, prefix=API_PREFIX)
app.include_router(products.router, prefix=API_PREFIX)
app.include_router(purchase_orders.router, prefix=API_PREFIX)
app.include_router(inventory.router, prefix=API_PREFIX)
app.include_router(deliveries.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)
app.include_router(reports.router, prefix=API_PREFIX)
app.include_router(audit.router, prefix=API_PREFIX)
app.include_router(company_settings.router, prefix=API_PREFIX)
app.include_router(currencies.router, prefix=API_PREFIX)
app.include_router(tax_rates.router, prefix=API_PREFIX)
app.include_router(purchase_requests.router, prefix=API_PREFIX)
app.include_router(approvals.router, prefix=API_PREFIX)
app.include_router(approval_admin.router, prefix=API_PREFIX)
app.include_router(po_amendments.router, prefix=API_PREFIX)
app.include_router(budgets.router, prefix=API_PREFIX)
app.include_router(catalog.router, prefix=API_PREFIX)
app.include_router(attachments.router, prefix=API_PREFIX)
app.include_router(supplier_returns.router, prefix=API_PREFIX)
app.include_router(supplier_invoices.router, prefix=API_PREFIX)
app.include_router(payment_runs.router, prefix=API_PREFIX)
app.include_router(payment_files.router, prefix=API_PREFIX)
app.include_router(exports.router, prefix=API_PREFIX)
app.include_router(gdpr.router, prefix=API_PREFIX)
app.include_router(search.router, prefix=API_PREFIX)
