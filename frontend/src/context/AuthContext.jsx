import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api, { TOKEN_KEY } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [household, setHousehold] = useState(null);
  const [loading, setLoading] = useState(Boolean(localStorage.getItem(TOKEN_KEY)));

  const loadHousehold = useCallback(async () => {
    try {
      const { data } = await api.get("/household");
      setHousehold(data.data);
      return data.data;
    } catch (err) {
      if (err.response?.status === 404) { setHousehold(null); return null; }
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setHousehold(null);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) return;
    (async () => {
      try {
        const { data } = await api.get("/auth/me");
        setUser(data.data.user);
        await loadHousehold();
      } catch {
        localStorage.removeItem(TOKEN_KEY);
      } finally {
        setLoading(false);
      }
    })();
  }, [loadHousehold]);

  useEffect(() => {
    window.addEventListener("auth:expired", logout);
    return () => window.removeEventListener("auth:expired", logout);
  }, [logout]);

  const authenticate = useCallback(async (path, body) => {
    const { data } = await api.post(path, body);
    localStorage.setItem(TOKEN_KEY, data.data.token);
    setUser(data.data.user);
    await loadHousehold();
    return data.data.user;
  }, [loadHousehold]);

  const value = useMemo(() => ({
    user, household, loading, setHousehold, refreshHousehold: loadHousehold, logout,
    login: (email, password) => authenticate("/auth/login", { email, password }),
    register: (name, email, password) => authenticate("/auth/register", { name, email, password }),
    isAdmin: user?.role === "ADMIN",
  }), [user, household, loading, loadHousehold, logout, authenticate]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
