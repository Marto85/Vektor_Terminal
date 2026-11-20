import { useCallback, useEffect, useMemo, useState } from "react";
import apiClient, { getStoredToken, setStoredToken } from "../api/client";
import { AuthContext } from "./authStore";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loadingAuth, setLoadingAuth] = useState(() =>
    Boolean(getStoredToken())
  );

  const logout = useCallback(() => {
    setStoredToken(null);
    setUser(null);
  }, []);

  const refreshProfile = useCallback(async () => {
    const token = getStoredToken();
    if (!token) {
      setUser(null);
      setLoadingAuth(false);
      return;
    }
    try {
      const res = await apiClient.get("/auth/me");
      setUser(res.data);
    } catch {
      setStoredToken(null);
      setUser(null);
    } finally {
      setLoadingAuth(false);
    }
  }, []);

  useEffect(() => {
    const token = getStoredToken();
    if (!token) return;

    let cancelled = false;
    apiClient
      .get("/auth/me")
      .then((res) => {
        if (!cancelled) setUser(res.data);
      })
      .catch(() => {
        if (!cancelled) {
          setStoredToken(null);
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingAuth(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
    };
    window.addEventListener("vektor:unauthorized", handleUnauthorized);
    return () =>
      window.removeEventListener("vektor:unauthorized", handleUnauthorized);
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await apiClient.post("/auth/login", { email, password });
    const { access_token, user: loggedUser } = res.data;
    setStoredToken(access_token);
    setUser(loggedUser);
    return loggedUser;
  }, []);

  const changePassword = useCallback(async (currentPassword, newPassword) => {
    const res = await apiClient.post("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
    if (res.data?.user) {
      setUser(res.data.user);
    }
    return res.data;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loadingAuth,
      isAuthenticated: Boolean(user),
      login,
      logout,
      changePassword,
      refreshProfile,
      isSuperAdmin: user?.role === "superadmin",
      isAdvisorOrAdmin:
        user?.role === "superadmin" || user?.role === "advisor",
      isClient: user?.role === "client",
    }),
    [user, loadingAuth, login, logout, changePassword, refreshProfile]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}