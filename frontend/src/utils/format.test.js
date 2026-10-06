import { addDays, errorMessage, kwh, localDate, money, pct, when } from "./format";

describe("formatters", () => {
  it("formats kWh, percentages and missing values", () => {
    expect(kwh(8.2)).toBe("8.20 kWh");
    expect(kwh(null)).toBe("–");
    expect(pct(42.68)).toBe("42.7%");
    expect(pct(42.68, 1, true)).toBe("+42.7%");
    expect(pct(-12, 0, true)).toBe("-12%");
  });

  it("shows currency for estimated cost and a prompt when no tariff exists", () => {
    expect(money({ amount: 1050.8, currency: "KES" })).toBe("KES 1,050.80");
    expect(money(null)).toBe("No tariff set");
  });

  it("renders times in Africa/Nairobi, not the browser zone", () => {
    expect(when("2026-03-26T00:00:00Z", { hour: "2-digit", minute: "2-digit", hour12: false })).toBe("03:00");
    expect(localDate("2026-03-31T22:00:00Z")).toBe("2026-04-01"); // already past midnight in Nairobi
  });

  it("adds days to a calendar date", () => {
    expect(addDays("2026-03-31", 1)).toBe("2026-04-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });
});

describe("errorMessage", () => {
  it("prefers the API message and appends field details", () => {
    const err = { response: { data: { error: { message: "Validation error", details: { household_size: "Must be an integer" } } } } };
    expect(errorMessage(err)).toBe("Validation error – household size: Must be an integer");
  });
  it("explains a network failure in plain language", () => {
    expect(errorMessage({ message: "Network Error" })).toMatch(/backend is running/);
  });
  it("falls back to a generic message", () => {
    expect(errorMessage({})).toMatch(/Something went wrong/);
  });
});
