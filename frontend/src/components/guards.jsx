import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Onboarding from "../pages/Onboarding";
import { LoadingBlock } from "./common";

/** Requires a logged-in user. With `needsHousehold`, shows onboarding until one exists. */
export function Protected({ children, needsHousehold = false, adminOnly = false }) {
  const { user, household, loading, isAdmin } = useAuth();
  const location = useLocation();
  if (loading) return <LoadingBlock label="Loading your account…" height="h-64" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (adminOnly && !isAdmin) return <Navigate to="/" replace />;
  if (needsHousehold && !household) return <Onboarding />;
  return children;
}

export function GuestOnly({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <LoadingBlock label="Loading…" height="h-screen" />;
  return user ? <Navigate to="/" replace /> : children;
}
