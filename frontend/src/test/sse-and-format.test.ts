import { describe, expect, it } from "vitest";
import { createSSEParser, type SSEEvent } from "@/lib/api";
import { formatDuration, formatKm, safeHref } from "@/lib/format";

describe("createSSEParser", () => {
  it("parses events split across arbitrary network chunks", () => {
    const events: SSEEvent[] = [];
    const feed = createSSEParser((e) => events.push(e));
    const stream = 'event: meta\r\ndata: {"conversation_id":"c1"}\r\n\r\n: ping\n\nevent: delta\ndata: {"text":"Hel"}\n\nevent: delta\ndata: {"text":"lo"}\n\nevent: final\ndata: {"answer":"Hello"}\n\n';
    for (let i = 0; i < stream.length; i += 7) feed(stream.slice(i, i + 7));
    expect(events.map((e) => e.event)).toEqual(["meta", "delta", "delta", "final"]);
    expect(JSON.parse(events[1].data).text).toBe("Hel");
    expect(JSON.parse(events[3].data).answer).toBe("Hello");
  });

  it("joins multi-line data fields", () => {
    const events: SSEEvent[] = [];
    createSSEParser((e) => events.push(e))("data: line1\ndata: line2\n\n");
    expect(events[0]).toEqual({ event: "message", data: "line1\nline2" });
  });
});

describe("format helpers", () => {
  it.each([
    ["https://example.com/a", "https://example.com/a"],
    ["/knowledge/demo/goa", "/knowledge/demo/goa"],
    ["javascript:alert(1)", null],
    ["data:text/html,x", null],
    ["//evil.com/x", null],
    ["", null],
  ])("safeHref(%s)", (input, expected) => {
    expect(safeHref(input)).toBe(expected);
  });

  it("formats durations and distances", () => {
    expect(formatDuration(14400)).toBe("4 h 0 min");
    expect(formatDuration(1500)).toBe("25 min");
    expect(formatDuration(null)).toBe("—");
    expect(formatKm(233000)).toBe("233 km");
    expect(formatKm(5400)).toBe("5.4 km");
  });
});
