import {
  Bell, BrainCircuit, LayoutDashboard, LogOut, Menu, Moon, Settings, ShieldCheck, Sun,
  TableProperties, TrendingUp, TriangleAlert, Upload, UserRound,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import Logo from "../components/Logo";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { get } from "../services/api";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/consumption", label: "Consumption", icon: TableProperties },
  { to: "/forecast", label: "Forecast", icon: TrendingUp },
  { to: "/anomalies", label: "Anomalies", icon: TriangleAlert },
  { to: "/import", label: "Data import", icon: Upload },
  { to: "/models", label: "Model performance", icon: BrainCircuit },
  { to: "/alerts", label: "Alerts", icon: Bell },
  { to: "/settings", label: "Settings", icon: Settings },
  { to: "/profile", label: "Profile", icon: UserRound },
];

function useUnreadAlerts() {
  const [count, setCount] = useState(0);
  const { pathname } = useLocation();
  useEffect(() => {
    let live = true;
    const load = () => get("/alerts", { per_page: 1 }).then((r) => live && setCount(r.unread_count || 0)).catch(() => {});
    load();
    const id = setInterval(load, 60000);
    return () => { live = false; clearInterval(id); };
  }, [pathname]);
  return count;
}

function NavItems({ isAdmin, unread, onNavigate }) {
  const items = isAdmin ? [...NAV, { to: "/admin", label: "Admin", icon: ShieldCheck }] : NAV;
  return (
    <nav className="flex flex-col gap-0.5 px-3" aria-label="Main">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={onNavigate}
          className={({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${isActive ? "bg-raised font-medium text-ink" : "text-mute hover:bg-raised/60 hover:text-ink"}`}>
          {({ isActive }) => (
            <>
              <Icon className={`h-[18px] w-[18px] ${isActive ? "text-amber" : ""}`} aria-hidden="true" />
              <span className="flex-1">{label}</span>
              {label === "Alerts" && unread > 0 && (
                <span className="rounded-full bg-sev-high px-1.5 py-0.5 text-[11px] font-semibold leading-none text-white">{unread > 99 ? "99+" : unread}</span>
              )}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

export default function AppLayout() {
  const { user, household, isAdmin, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const unread = useUnreadAlerts();
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => setOpen(false), [pathname]);

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[15rem_1fr]">
      <aside className="sticky top-0 hidden h-screen flex-col gap-6 border-r border-line bg-panel py-5 lg:flex">
        <div className="px-5"><Link to="/"><Logo /></Link></div>
        <NavItems isAdmin={isAdmin} unread={unread} />
        <p className="mt-auto px-5 text-xs leading-relaxed text-faint">
          Forecasts and anomaly flags are statistical estimates, not meter-verified faults.
        </p>
      </aside>

      {open && (
        <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 bg-black/55" onClick={() => setOpen(false)} />
          <aside className="slide-in relative flex h-full w-64 flex-col gap-6 border-r border-line bg-panel py-5">
            <div className="px-5"><Logo /></div>
            <NavItems isAdmin={isAdmin} unread={unread} onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-base/85 px-4 backdrop-blur sm:px-6">
          <button className="rounded-md p-1.5 text-mute hover:bg-raised lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation">
            <Menu className="h-5 w-5" />
          </button>
          <div className="min-w-0 flex-1 truncate text-sm text-mute">
            {household ? <>{household.household_name}{household.location ? `, ${household.location}` : ""}</> : "No household yet"}
          </div>
          <Link to="/alerts" className="relative rounded-md p-2 text-mute hover:bg-raised hover:text-ink" aria-label={`Alerts${unread ? `, ${unread} unread` : ""}`}>
            <Bell className="h-[18px] w-[18px]" />
            {unread > 0 && <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-sev-high" />}
          </Link>
          <button onClick={toggle} className="rounded-md p-2 text-mute hover:bg-raised hover:text-ink" aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
            {theme === "dark" ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}
          </button>
          <div className="hidden items-center gap-2 border-l border-line pl-3 sm:flex">
            <span className="text-sm">{user?.name}</span>
            <button onClick={() => { logout(); navigate("/login"); }} className="rounded-md p-2 text-mute hover:bg-raised hover:text-ink" aria-label="Log out" title="Log out">
              <LogOut className="h-[18px] w-[18px]" />
            </button>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:py-8"><Outlet /></main>
      </div>
    </div>
  );
}
