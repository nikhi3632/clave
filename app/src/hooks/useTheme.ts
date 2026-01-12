"use client";

import { createContext, useContext } from "react";

export type Theme = "light" | "dark";

export interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext);
  // Return default values for SSR/static generation
  if (context === undefined) {
    return { theme: "light", toggleTheme: () => {} };
  }
  return context;
}
