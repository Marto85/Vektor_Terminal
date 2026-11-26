import { useEffect, useState } from "react";
import { ThemeContext } from "./themeStore";

const THEME_STORAGE_KEY = "vektor_theme";

function resolveIsDark(pref) {
  if (pref === "dark") return true;
  if (pref === "light") return false;
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  return false;
}

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try {
      const saved = localStorage.getItem(THEME_STORAGE_KEY);
      return saved === "dark" || saved === "light" || saved === "system" ? saved : "system";
    } catch {
      return "system";
    }
  });

  const [systemPrefersDark, setSystemPrefersDark] = useState(() => resolveIsDark("system"));

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return undefined;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = (e) => setSystemPrefersDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const isDark = theme === "dark" || (theme === "system" && systemPrefersDark);

  useEffect(() => {
    const root = document.documentElement;
    if (isDark) {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (metaTheme) {
      metaTheme.setAttribute("content", isDark ? "#18181b" : "#252526");
    }
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      // ignore storage errors
    }
  }, [theme, isDark]);

  const toggleTheme = () => {
    setTheme((prev) => {
      if (prev === "light") return "dark";
      if (prev === "dark") return "light";
      return systemPrefersDark ? "light" : "dark";
    });
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        isDark,
        toggleTheme,
        setTheme,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}
