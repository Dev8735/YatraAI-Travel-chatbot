import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CitationList } from "@/components/Citations";
import { RichText } from "@/components/RichText";
import type { Citation } from "@/lib/types";

const cite = (id: string, url: string, extra: Partial<Citation> = {}): Citation =>
  ({ id, url, title: `Title ${id}`, snippet: "snippet", is_demo: false, ...extra });

describe("RichText", () => {
  it("renders known citation markers as buttons and drops unknown ones", async () => {
    const onCite = vi.fn();
    render(<RichText text="Fact one [S1]. Fake fact [S7]." citations={[cite("S1", "https://a.com")]} onCite={onCite} />);
    const btn = screen.getByRole("button", { name: "Source 1" });
    await userEvent.click(btn);
    expect(onCite).toHaveBeenCalledWith("S1");
    expect(screen.queryByText(/S7/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Source 7" })).not.toBeInTheDocument();
  });

  it("never interprets markup from model or source text", () => {
    const { container } = render(<RichText text={'<img src=x onerror="alert(1)"> <script>alert(2)</script> **bold**'} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
    expect(screen.getByText("bold").tagName).toBe("STRONG");
  });

  it("renders bullet lists with a lead line", () => {
    render(<RichText text={"Here is what the sources say:\n- One\n- Two"} />);
    expect(screen.getByText("Here is what the sources say:").tagName).toBe("P");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });
});

describe("CitationList", () => {
  it("links external sources safely and internal demo sources in-app", () => {
    render(<CitationList citations={[cite("S1", "https://example.com/page"), cite("S2", "/knowledge/demo/jaipur", { is_demo: true })]} />);
    const links = screen.getAllByRole("link");
    expect(links[0]).toHaveAttribute("href", "https://example.com/page");
    expect(links[0]).toHaveAttribute("target", "_blank");
    expect(links[0].getAttribute("rel")).toContain("noopener");
    expect(links[1]).toHaveAttribute("href", "/knowledge/demo/jaipur");
    expect(screen.getByText("Demo content")).toBeInTheDocument();
  });

  it("does not create links for unsafe URL schemes", () => {
    render(<CitationList citations={[cite("S1", "javascript:alert(1)")]} />);
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getByText("Title S1")).toBeInTheDocument();
  });
});
