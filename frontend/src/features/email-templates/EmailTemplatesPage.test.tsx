import { fireEvent, screen, waitFor } from "@testing-library/react";
import { AxiosError, type AxiosResponse } from "axios";
import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/api/client";
import type { EmailTemplate } from "@/api/emailTemplates";
import { mockGet, renderWithProviders } from "@/test/render";

import { EmailTemplatesPage } from "./EmailTemplatesPage";

function template(overrides: Partial<EmailTemplate> = {}): EmailTemplate {
  return {
    key: "po_sent",
    label: "Purchase order to supplier",
    variables: ["po_number", "company_name"],
    subject: "Order {{ po_number }}",
    body: "Hello from {{ company_name }}",
    is_customised: true,
    default_subject: "Purchase order {{ po_number }}",
    default_body: "Please find the order attached.",
    ...overrides,
  };
}

function show(templates: EmailTemplate[]) {
  mockGet({ "/email-templates": templates });
  renderWithProviders(<EmailTemplatesPage />, { permissions: ["settings:manage"] });
}

describe("EmailTemplatesPage", () => {
  afterEach(() => vi.restoreAllMocks());

  it("shows the template, its allowed variables as chips and the customised badge", async () => {
    show([template()]);

    expect(await screen.findByLabelText(/^Subject/)).toHaveValue("Order {{ po_number }}");
    expect(screen.getByText("{{ po_number }}", { selector: "code" })).toBeInTheDocument();
    expect(screen.getByText("{{ company_name }}", { selector: "code" })).toBeInTheDocument();
    expect(screen.getByText("Customised")).toBeInTheDocument();
  });

  it("shows the server's 422 detail inline and keeps the edit", async () => {
    show([template()]);
    vi.spyOn(apiClient, "put").mockRejectedValue(
      new AxiosError("bad", "ERR_BAD_REQUEST", undefined, undefined, {
        status: 422,
        data: { detail: "Unknown variable: {{ nope }}" },
      } as AxiosResponse),
    );

    fireEvent.change(await screen.findByLabelText(/^Subject/), { target: { value: "Hi {{ nope }}" } });
    fireEvent.click(screen.getByRole("button", { name: "Save template" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Unknown variable: {{ nope }}");
    expect(screen.getByLabelText(/^Subject/)).toHaveValue("Hi {{ nope }}");
  });

  it("saves the edited subject and body", async () => {
    show([template()]);
    const put = vi.spyOn(apiClient, "put").mockResolvedValue({ data: template({ subject: "New subject" }) });

    fireEvent.change(await screen.findByLabelText(/^Subject/), { target: { value: "New subject" } });
    fireEvent.click(screen.getByRole("button", { name: "Save template" }));

    await waitFor(() =>
      expect(put).toHaveBeenCalledWith("/email-templates/po_sent", {
        subject: "New subject",
        body: "Hello from {{ company_name }}",
      }),
    );
  });

  it("resets to default only after confirmation", async () => {
    show([template()]);
    const del = vi.spyOn(apiClient, "delete").mockResolvedValue({
      data: template({ is_customised: false, subject: "Purchase order {{ po_number }}" }),
    });

    fireEvent.click(await screen.findByRole("button", { name: "Reset to default" }));
    expect(del).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));

    await waitFor(() => expect(del).toHaveBeenCalledWith("/email-templates/po_sent"));
  });

  it("cannot reset a template that is not customised", async () => {
    show([template({ is_customised: false })]);

    expect(await screen.findByRole("button", { name: "Reset to default" })).toBeDisabled();
    expect(screen.queryByText("Customised")).not.toBeInTheDocument();
  });
});
