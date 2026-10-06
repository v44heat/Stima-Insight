import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ConsumptionChart from "./ConsumptionChart";

vi.mock("../context/ThemeContext", () => ({
  useTheme: () => ({ colors: { actual: "#fff", expected: "#09f", forecast: "#fb0", band: "#fb0", grid: "#222", axis: "#999", HIGH: "#f55", panel: "#111" } }),
}));
// Recharts needs real layout; jsdom has none, so stub the container to a fixed size.
vi.mock("recharts", async (orig) => {
  const mod = await orig();
  return { ...mod, ResponsiveContainer: ({ children }) => <div style={{ width: 600, height: 300 }}>{mod.ComposedChart ? children : null}</div> };
});

const points = [
  { timestamp: "2026-03-01T00:00:00+03:00", actual: 0.4, expected: 0.38, forecast: null, lower: null, upper: null, anomaly_severity: null },
  { timestamp: "2026-03-01T01:00:00+03:00", actual: 2.2, expected: 0.3, forecast: null, lower: null, upper: null, anomaly_severity: "CRITICAL", anomaly_id: 7 },
  { timestamp: "2026-04-01T00:00:00+03:00", actual: null, expected: null, forecast: 0.5, lower: 0.4, upper: 0.7, anomaly_severity: null },
];

describe("ConsumptionChart", () => {
  it("offers a legend entry only for series present in the data", () => {
    render(<ConsumptionChart points={points} />);
    for (const label of ["Actual", "Expected", "Forecast", "90% range", "Anomalies"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
  });

  it("omits legend entries for series that have no data", () => {
    render(<ConsumptionChart points={[points[0]]} />);
    expect(screen.queryByRole("button", { name: "Forecast" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Anomalies" })).toBeNull();
  });

  it("lets a series be toggled off and on", async () => {
    render(<ConsumptionChart points={points} />);
    const btn = screen.getByRole("button", { name: "Expected" });
    expect(btn).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(btn);
    expect(btn).toHaveAttribute("aria-pressed", "false");
  });

  it("respects the `show` prop for hidden series", () => {
    render(<ConsumptionChart points={points} show={{ forecast: false, band: false }} />);
    expect(screen.queryByRole("button", { name: "Forecast" })).toBeNull();
    expect(screen.queryByRole("button", { name: "90% range" })).toBeNull();
  });
});
