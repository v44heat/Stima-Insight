import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Drawer, Field, Pagination, SeverityBadge } from "./common";

describe("SeverityBadge", () => {
  it("shows a readable label", () => {
    render(<SeverityBadge severity="CRITICAL" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });
});

describe("Field", () => {
  it("links the label to its input", () => {
    render(<Field label="Email"><input type="email" /></Field>);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });
  it("marks the input invalid and shows the error", () => {
    render(<Field label="Name" error="Required"><input /></Field>);
    expect(screen.getByLabelText("Name")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Required")).toBeInTheDocument();
  });
});

describe("Pagination", () => {
  it("moves between pages and disables the edges", async () => {
    const onPage = vi.fn();
    render(<Pagination pagination={{ page: 1, pages: 3, total: 60, per_page: 25 }} onPage={onPage} />);
    expect(screen.getByLabelText("Previous page")).toBeDisabled();
    await userEvent.click(screen.getByLabelText("Next page"));
    expect(onPage).toHaveBeenCalledWith(2);
  });
});

describe("Drawer", () => {
  it("closes on Escape", async () => {
    const onClose = vi.fn();
    render(<Drawer open onClose={onClose} title="Details">content</Drawer>);
    expect(screen.getByRole("dialog", { name: "Details" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
  it("renders nothing when closed", () => {
    render(<Drawer open={false} onClose={() => {}} title="Details">content</Drawer>);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
