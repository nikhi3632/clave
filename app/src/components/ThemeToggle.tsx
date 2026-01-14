"use client";

import { useTheme } from "@/hooks/useTheme";
import { MoonIcon, SunIcon } from "./ui/Icon";
import { themeToggleStyles as styles } from "@/styles/shared";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={styles.button}
      aria-label={`Switch to ${theme === "light" ? "dark" : "light"} mode`}
    >
      {theme === "light" ? (
        <MoonIcon className={styles.icon} />
      ) : (
        <SunIcon className={styles.icon} />
      )}
    </button>
  );
}
