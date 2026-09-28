import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, tokens } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(tokens.access));

  useEffect(() => {
    if (!tokens.access) return;
    api("/auth/me/")
      .then(setUser)
      .catch(() => tokens.clear())
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener("gatepass:logout", onLogout);
    return () => window.removeEventListener("gatepass:logout", onLogout);
  }, []);

  const login = useCallback(async (username, password) => {
    tokens.set(await api("/auth/login/", { method: "POST", body: { username, password }, auth: false }));
    setUser(await api("/auth/me/"));
  }, []);

  const register = useCallback(
    async ({ username, email, password }) => {
      await api("/auth/register/", { method: "POST", body: { username, email, password }, auth: false });
      await login(username, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    tokens.clear();
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
