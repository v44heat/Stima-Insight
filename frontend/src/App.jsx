import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { LoadingBlock } from "./components/common";
import { GuestOnly, Protected } from "./components/guards";
import AppLayout from "./layouts/AppLayout";
import { Login, Register } from "./pages/AuthPages";

const Admin = lazy(() => import("./pages/Admin"));
const Alerts = lazy(() => import("./pages/Alerts"));
const Anomalies = lazy(() => import("./pages/Anomalies"));
const Consumption = lazy(() => import("./pages/Consumption"));
const Dashboard = lazy(() => import("./pages/Dashboard"));
const DataImport = lazy(() => import("./pages/DataImport"));
const Forecast = lazy(() => import("./pages/Forecast"));
const ModelPerformance = lazy(() => import("./pages/ModelPerformance"));
const Profile = lazy(() => import("./pages/Profile"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));

export default function App() {
  const withHousehold = (el) => <Protected needsHousehold>{el}</Protected>;
  return (
    <Suspense fallback={<LoadingBlock label="Loading…" height="h-screen" />}>
    <Routes>
      <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
      <Route path="/register" element={<GuestOnly><Register /></GuestOnly>} />
      <Route element={<Protected><AppLayout /></Protected>}>
        <Route index element={withHousehold(<Dashboard />)} />
        <Route path="consumption" element={withHousehold(<Consumption />)} />
        <Route path="forecast" element={withHousehold(<Forecast />)} />
        <Route path="anomalies" element={withHousehold(<Anomalies />)} />
        <Route path="import" element={withHousehold(<DataImport />)} />
        <Route path="models" element={withHousehold(<ModelPerformance />)} />
        <Route path="alerts" element={withHousehold(<Alerts />)} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="profile" element={<Profile />} />
        <Route path="admin" element={<Protected adminOnly><Admin /></Protected>} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
  );
}
