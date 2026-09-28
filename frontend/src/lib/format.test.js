import { describe, expect, it } from "vitest";
import { firstErrorMessage } from "./api";
import { formatNaira, fromLocalInput, minutesLeft, nairaToKobo, orderTotalLabel, toLocalInput } from "./format";

describe("money", () => {
  it("formats kobo as naira", () => {
    expect(formatNaira(0)).toBe("Free");
    expect(formatNaira(500_000)).toMatch(/5,000/);
    expect(formatNaira(12_550)).toMatch(/125\.5/);
    expect(formatNaira(null)).toBe("");
  });

  it("converts naira input to kobo without float errors", () => {
    expect(nairaToKobo("5000")).toBe(500_000);
    expect(nairaToKobo("1,500")).toBe(150_000);
    expect(nairaToKobo("19.99")).toBe(1999);
    expect(Number.isNaN(nairaToKobo("abc"))).toBe(true);
  });
});

describe("datetime-local round trip", () => {
  it("keeps the same instant", () => {
    const iso = new Date(2026, 9, 10, 18, 30).toISOString();
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso);
    expect(toLocalInput(null)).toBe("");
    expect(fromLocalInput("")).toBe(null);
  });
});

describe("minutesLeft", () => {
  it("rounds up and never goes negative", () => {
    const now = Date.parse("2026-01-01T10:00:00Z");
    expect(minutesLeft("2026-01-01T10:14:10Z", now)).toBe(15);
    expect(minutesLeft("2026-01-01T09:00:00Z", now)).toBe(0);
  });
});

describe("orderTotalLabel", () => {
  it("counts tickets across items", () => {
    expect(orderTotalLabel([{ quantity: 2 }, { quantity: 1 }])).toBe("3 tickets");
    expect(orderTotalLabel([{ quantity: 1 }])).toBe("1 ticket");
  });
});

describe("firstErrorMessage", () => {
  it("reads DRF error shapes", () => {
    expect(firstErrorMessage({ detail: "VIP is sold out." })).toBe("VIP is sold out.");
    expect(firstErrorMessage({ price: ["Too low."] })).toBe("price: Too low.");
  });
});
