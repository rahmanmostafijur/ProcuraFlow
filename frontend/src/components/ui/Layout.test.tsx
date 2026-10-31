import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { Button } from "./Button";
import { Card } from "./Card";
import { Divider } from "./Divider";
import { EmptyState } from "./EmptyState";
import { Illustration } from "./Illustration";
import { ILLUSTRATION_NAMES } from "./illustration-names";
import { PageHeader } from "./PageHeader";
import { Skeleton, SkeletonText } from "./Skeleton";
import { Spinner } from "./Spinner";
import { Stat } from "./Stat";
import { VisuallyHidden } from "./VisuallyHidden";

describe("PageHeader", () => {
  it("renders the title as the page heading, breadcrumbs with the current page marked, and one primary action", () => {
    render(
      <MemoryRouter>
        <PageHeader
          title="Purchase orders"
          description="All orders"
          breadcrumbs={[{ label: "Buy", to: "/buy" }, { label: "Purchase orders" }]}
          primaryAction={<Button>New order</Button>}
          secondaryActions={<Button variant="secondary">Export</Button>}
        />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Purchase orders" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(nav).toHaveTextContent("Buy");
    expect(screen.getByRole("link", { name: "Buy" })).toHaveAttribute("href", "/buy");
    expect(
      screen.getAllByText("Purchase orders").find((el) => el.getAttribute("aria-current") === "page"),
    ).toBeDefined();
    expect(screen.getByRole("button", { name: "New order" })).toBeInTheDocument();
  });
});

describe("EmptyState and illustrations", () => {
  it("ships at least six original illustrations, all decorative", () => {
    expect(ILLUSTRATION_NAMES.length).toBeGreaterThanOrEqual(6);
    for (const name of ILLUSTRATION_NAMES) {
      const { container, unmount } = render(<Illustration name={name} />);
      const svg = container.querySelector("svg")!;
      expect(svg).toHaveAttribute("aria-hidden", "true");
      expect(svg.getAttribute("class")).not.toContain("slate");
      expect(svg.innerHTML).not.toMatch(/#[0-9a-f]{3,6}/i);
      unmount();
    }
  });

  it("shows title, description, action and an illustration", () => {
    const { container } = render(
      <EmptyState
        illustration="orders"
        title="No orders yet"
        description="Create the first one"
        action={<Button>Create</Button>}
      />,
    );
    expect(screen.getByText("No orders yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeInTheDocument();
    expect(container.querySelector('svg[aria-hidden="true"]')).not.toBeNull();
  });

  it("keeps the legacy icon fallback", () => {
    const { container } = render(<EmptyState title="Nothing" />);
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });
});

describe("small layout pieces", () => {
  it("hides skeletons from assistive technology", () => {
    const { container } = render(
      <>
        <Skeleton />
        <SkeletonText lines={2} />
      </>,
    );
    expect(container.querySelectorAll('[aria-hidden="true"]').length).toBeGreaterThanOrEqual(2);
  });

  it("announces a labelled spinner and hides a bare one", () => {
    const { container, rerender } = render(<Spinner label="Saving" />);
    expect(screen.getByRole("status")).toHaveTextContent("Saving");
    rerender(<Spinner />);
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("renders a stat as a labelled figure with tabular numerals", () => {
    render(<Stat label="Open orders" value="42" hint="3 overdue" />);
    expect(screen.getByText("Open orders")).toBeInTheDocument();
    expect(screen.getByText("42")).toHaveAttribute("data-kpi");
  });

  it("renders a divider separator, a card and visually hidden text", () => {
    render(
      <>
        <Divider orientation="vertical" />
        <Card padding="md">inside</Card>
        <VisuallyHidden>for screen readers</VisuallyHidden>
      </>,
    );
    expect(screen.getByRole("separator")).toHaveAttribute("aria-orientation", "vertical");
    expect(screen.getByText("inside").className).toContain("bg-surface");
    expect(screen.getByText("for screen readers")).toHaveClass("sr-only");
  });
});
