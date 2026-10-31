from dataclasses import dataclass

from jinja2 import StrictUndefined, TemplateError, meta
from jinja2.sandbox import SandboxedEnvironment

# Plain text mail: autoescape would only mangle ampersands and quotes in names, and nothing here is HTML.
_ENV = SandboxedEnvironment(autoescape=False, undefined=StrictUndefined, keep_trailing_newline=True)

MAX_SUBJECT_LENGTH = 300
MAX_BODY_LENGTH = 10_000


class TemplateRenderError(ValueError):
    pass


@dataclass(frozen=True)
class TemplateDefinition:
    key: str
    label: str
    variables: tuple[str, ...]
    subject: str
    body: str


TEMPLATES: dict[str, TemplateDefinition] = {
    t.key: t
    for t in (
        TemplateDefinition(
            key="invitation",
            label="Invitation",
            variables=("full_name", "company_name", "link", "expires_in"),
            subject="You are invited to {{ company_name }}",
            body=(
                "Hello {{ full_name }},\n\n"
                "You have been invited to {{ company_name }} on ProcuraFlow. "
                "Choose your password here: {{ link }}\n\n"
                "The link works once and expires in {{ expires_in }}.\n"
            ),
        ),
        TemplateDefinition(
            key="password_reset",
            label="Password reset",
            variables=("full_name", "link", "expires_in"),
            subject="Reset your ProcuraFlow password",
            body=(
                "Hello {{ full_name }},\n\n"
                "Someone asked to reset the password for this account. If it was you, use this link: {{ link }}\n\n"
                "It works once and expires in {{ expires_in }}. If it was not you, ignore this message.\n"
            ),
        ),
        TemplateDefinition(
            key="approval_needed",
            label="Approval needed",
            variables=("full_name", "document_type", "document_number", "amount", "link"),
            subject="Approval needed: {{ document_type }} {{ document_number }}",
            body=(
                "Hello {{ full_name }},\n\n"
                "{{ document_type }} {{ document_number }} for {{ amount }} is waiting for your approval: {{ link }}\n"
            ),
        ),
        TemplateDefinition(
            key="po_to_supplier",
            label="Purchase order to supplier",
            variables=("supplier_name", "po_number", "company_name", "total", "delivery_date"),
            subject="Purchase order {{ po_number }} from {{ company_name }}",
            body=(
                "Dear {{ supplier_name }},\n\n"
                "We have issued purchase order {{ po_number }}, total {{ total }}. "
                "Expected delivery: {{ delivery_date }}.\n\n"
                "Regards,\n{{ company_name }}\n"
            ),
        ),
        TemplateDefinition(
            key="invoice_exception",
            label="Invoice exception",
            variables=("full_name", "invoice_number", "supplier_name", "reasons", "link"),
            subject="Invoice {{ invoice_number }} needs a decision",
            body=(
                "Hello {{ full_name }},\n\n"
                "Invoice {{ invoice_number }} from {{ supplier_name }} did not match: {{ reasons }}.\n"
                "Review it here: {{ link }}\n"
            ),
        ),
    )
}


def _undeclared(source: str) -> set[str]:
    try:
        return meta.find_undeclared_variables(_ENV.parse(source))
    except TemplateError as exc:
        raise TemplateRenderError(f"Template syntax error: {exc}") from exc


def validate_template(key: str, subject: str, body: str) -> None:
    """Reject unknown keys, oversized text, syntax errors and variables outside the template's fixed list."""
    definition = TEMPLATES.get(key)
    if definition is None:
        raise TemplateRenderError(f"Unknown template '{key}'")
    if len(subject) > MAX_SUBJECT_LENGTH or len(body) > MAX_BODY_LENGTH:
        raise TemplateRenderError("Template is too long")
    if "\n" in subject or "\r" in subject:
        raise TemplateRenderError("Subject must be a single line")
    unknown = (_undeclared(subject) | _undeclared(body)) - set(definition.variables)
    if unknown:
        raise TemplateRenderError(f"Unknown variables: {', '.join(sorted(unknown))}")


def render_template(key: str, subject: str, body: str, context: dict[str, str]) -> tuple[str, str]:
    validate_template(key, subject, body)
    allowed = {name: context[name] for name in TEMPLATES[key].variables if name in context}
    try:
        rendered_subject = _ENV.from_string(subject).render(**allowed).strip()
        rendered_body = _ENV.from_string(body).render(**allowed)
    except TemplateError as exc:
        raise TemplateRenderError(f"Template could not be rendered: {exc}") from exc
    # A variable holding a newline must not be able to add mail headers through the subject.
    return " ".join(rendered_subject.split()), rendered_body
