import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import RangeGrid from "./RangeGrid";

describe("RangeGrid", () => {
  it("renders 169 grid cells", () => {
    render(<RangeGrid />);
    const buttons = document.querySelectorAll("button.aspect-square");
    expect(buttons.length).toBe(169);
  });

  it("renders position and stack selectors", () => {
    const { container } = render(<RangeGrid />);
    const text = container.textContent || "";
    expect(text).toContain("Position");
    expect(text).toContain("Stack");
    expect(text).toContain("BTN");
    expect(text).toContain("100bb");
  });

  it("shows legend counts", () => {
    const { container } = render(<RangeGrid />);
    const text = container.textContent || "";
    expect(text).toContain("Raise (");
    expect(text).toContain("Call (");
    expect(text).toContain("Fold (");
  });

  it("shows hover hint when no selection", () => {
    const { container } = render(<RangeGrid />);
    expect(container.textContent).toContain("Hover or tap a hand");
  });
});
