import { useCallback, useEffect, useMemo, useState } from "react";
import apiClient, { getStoredToken, setStoredToken } from "../api/client";
import { AuthContext } from "./authStore";

function consumeInitialUrlAuthParams() {
  if (typeof window === "undefined") {
    return { oauthToken: null, oauthError: null, resetToken: null };
  }
  const url = new URL(window.location.href);
  const oauthToken = url.searchParams.get("oauth_token");
  const oauthError = url.searchParams.get("oauth_error");
  const resetToken = url.searchParams.get("reset_token");

  if (oauthToken || oauthError) {
    url.searchParams.delete("oauth_token");
    url.searchParams.delete("oauth_error");
    window.history.replaceState({}, "", url.pathname + url.search + url.hash);
  }
  return { oauthToken, oauthError, resetToken };
}

export function AuthProvider({ children }) {
  const [initialUrlParams] = useState(() => consumeInitialUrlAuthParams());

  const [user, setUser] = useState(null);
  const [oauthError, setOauthError] = useState(
    () => initialUrlParams.oauthError || ""
  );
  const [pendingResetToken, setPendingResetToken] = useState(
    () => initialUrlParams.resetToken || ""
  );
  const [loadingAuth, setLoadingAuth] = useState(() =>
    Boolean(initialUrlParams.oauthToken || getStoredToken())
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
    if (initialUrlParams.oauthToken) {
      setStoredToken(initialUrlParams.oauthToken);
    }
    const token = initialUrlParams.oauthToken || getStoredToken();
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
  }, [initialUrlParams.oauthToken]);

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
    };
    window.addEventListener("vektor:unauthorized", handleUnauthorized);
    return () =>
      window.removeEventListener("vektor:unauthorized", handleUnauthorized);
  }, []);

 const login = useCallback(async (identifier, password) => {
    const cleanId = (identifier || "").trim();
    const res = await apiClient.post("/auth/login", {
      email: cleanId,
      password,
    });
    const { access_token, user: loggedUser } = res.data;
    setStoredToken(access_token);
    setUser(loggedUser);
    return loggedUser;
  }, []);

  const registerPublic = useCallback(
    async ({ username, email, full_name, password }) => {
      const res = await apiClient.post("/auth/register", {
        username,
        email,
        full_name,
        password,
      });
      const { access_token, user: createdUser } = res.data;
      setStoredToken(access_token);
      setUser(createdUser);
      return createdUser;
    },
    []
  );

  const requestRecovery = useCallback(async (email) => {
    const res = await apiClient.post("/auth/forgot-password", { email });
    return res.data;
  }, []);

  const resetPasswordWithToken = useCallback(async (token, newPassword) => {
    const res = await apiClient.post("/auth/reset-password", {
      token,
      new_password: newPassword,
    });
    const { access_token, user: updatedUser } = res.data;
    setStoredToken(access_token);
    setUser(updatedUser);
    setPendingResetToken("");
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      if (url.searchParams.has("reset_token")) {
        url.searchParams.delete("reset_token");
        window.history.replaceState({}, "", url.pathname + url.search + url.hash);
      }
    }
    return updatedUser;
  }, []);

  const startOAuthLogin = useCallback(async (provider) => {
    const res = await apiClient.get(`/auth/oauth/${provider}/login`);
    if (res.data?.authorize_url) {
      window.location.href = res.data.authorize_url;
    }
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
      oauthError,
      clearOauthError: () => setOauthError(""),
      pendingResetToken,
      clearPendingResetToken: () => setPendingResetToken(""),
      login,
      registerPublic,
      requestRecovery,
      resetPasswordWithToken,
      startOAuthLogin,
      logout,
      changePassword,
      refreshProfile,
      isSuperAdmin: user?.role === "superadmin",
      isAdvisorOrAdmin:
        user?.role === "superadmin" || user?.role === "advisor",
      isClient: user?.role === "client",
    }),
    [
      user,
      loadingAuth,
      oauthError,
      pendingResetToken,
      login,
      registerPublic,
      requestRecovery,
      resetPasswordWithToken,
      startOAuthLogin,
      logout,
      changePassword,
      refreshProfile,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}