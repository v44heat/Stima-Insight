import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const ThemeContext = createContext(null);

/** Hex colours for SVG charts (CSS variables don't resolve in SVG attributes). */
export const CHART_COLORS = {
  dark: {
    actual: "#e8ecf4", expected: "#5aa9ff", forecast: "#f2b63d", band: "#f2b63d", grid: "#26304a", axis: "#97a2bc",
    LOW: "#e6d36a", MEDIUM: "#f59e4b", HIGH: "#ef5a5a", CRITICAL: "#ff3d8b", panel: "#161c29",
  },
  light: {
    actual: "#161c29", expected: "#1d6ad6", forecast: "#b07000", band: "#b07000", grid: "#dce0ea", axis: "#5c667d",
    LOW: "#948600", MEDIUM: "#c46200", HIGH: "#ce2828", CRITICAL: "#be125a", panel: "#ffffff",
  },
};

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => (localStorage.getItem("theme") === "light" ? "light" : "dark"));

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  const value = useMemo(() => ({ theme, setTheme, toggle, colors: CHART_COLORS[theme] }), [theme, toggle]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
