import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { AppShell } from "@/components/shell/AppShell";

const renderShell = () =>
  render(
    <AppShell>
      <p>page</p>
    </AppShell>,
  );

beforeEach(() => localStorage.clear());

describe("AppShell sidebar", () => {
  it("collapses to an icon rail and back; the choice is remembered", () => {
    renderShell();
    const sidebar = screen.getByTestId("sidebar");
    expect(sidebar).toHaveAttribute("data-collapsed", "false");
    expect(sidebar).toHaveTextContent("Lịch sử run");

    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    expect(sidebar).toHaveAttribute("data-collapsed", "true");
    expect(sidebar).not.toHaveTextContent("Lịch sử run");
    // the label stays reachable for screen readers and the tooltip
    expect(screen.getByRole("link", { name: "Lịch sử run" })).toBeInTheDocument();
    expect(localStorage.getItem("sme.sidebar")).toBe("collapsed");

    fireEvent.click(screen.getByTestId("sidebar-toggle"));
    expect(sidebar).toHaveAttribute("data-collapsed", "false");
    expect(localStorage.getItem("sme.sidebar")).toBe("expanded");
  });

  it("Ctrl/Cmd+B toggles it; a reload starts collapsed when it was left collapsed", () => {
    const { unmount } = renderShell();
    fireEvent.keyDown(window, { key: "b", ctrlKey: true });
    expect(screen.getByTestId("sidebar")).toHaveAttribute("data-collapsed", "true");
    unmount();

    renderShell();
    expect(screen.getByTestId("sidebar")).toHaveAttribute("data-collapsed", "true");
  });
});
