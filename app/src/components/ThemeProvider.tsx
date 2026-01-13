"use client";

import { useEffect, useRef, useState } from "react";
import { ThemeContext, Theme } from "@/hooks/useTheme";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("light");
  const mounted = useRef(false);

  // Hydration: read theme from localStorage on mount (valid pattern for SSR)
  useEffect(() => {
    mounted.current = true;
    try {
      const stored = localStorage.getItem("theme") as Theme | null;
      if (stored) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setTheme(stored);
      } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
        setTheme("dark");
      }
    } catch {
      // localStorage not available (incognito mode, etc.)
    }
  }, []);

  useEffect(() => {
    if (!mounted.current) return;

    const root = document.documentElement;
    if (theme === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
    try {
      localStorage.setItem("theme", theme);
    } catch {
      // localStorage not available
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
