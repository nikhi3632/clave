/**
 * DataQualityModal component styles
 */

import { modalStyles, spinnerStyles, statCardStyles } from "./shared";

export const dataQualityModalStyles = {
  // Base modal styles
  ...modalStyles,

  // Override container for data quality specific sizing
  container: [
    modalStyles.container,
    "w-full max-w-2xl mx-4",
  ].join(" "),

  // Summary stats grid
  statsGrid: "grid grid-cols-3 gap-4",
  statCard: statCardStyles,

  // Source breakdown
  sectionTitle: "text-sm font-medium text-slate-900 dark:text-zinc-100 mb-3",
  sourceList: "space-y-2",
  sourceRow: [
    "flex items-center justify-between py-2 px-3 rounded-lg",
    "bg-slate-50 dark:bg-zinc-800",
  ].join(" "),
  sourceName: "font-medium text-slate-700 dark:text-zinc-300",
  sourceStats: "text-slate-600 dark:text-zinc-400",

  // Data quality indicators
  qualityGrid: "grid grid-cols-3 gap-3",
  qualityCard: (hasIssues: boolean, severity: "error" | "warning") => {
    if (!hasIssues) return "p-3 rounded-lg bg-green-50 dark:bg-green-900/20";
    return severity === "error"
      ? "p-3 rounded-lg bg-red-50 dark:bg-red-900/20"
      : "p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20";
  },
  qualityValue: (hasIssues: boolean, severity: "error" | "warning") => {
    if (!hasIssues) return "text-lg font-bold text-green-600 dark:text-green-400";
    return severity === "error"
      ? "text-lg font-bold text-red-600 dark:text-red-400"
      : "text-lg font-bold text-amber-600 dark:text-amber-400";
  },
  qualityLabel: "text-xs text-slate-600 dark:text-zinc-400",

  // Date range footer
  dateRange: [
    "text-center text-sm pt-2",
    "text-slate-500 dark:text-zinc-400",
    "border-t border-slate-200 dark:border-zinc-800",
  ].join(" "),

  // Loading/error states
  loading: spinnerStyles,
  error: "text-center py-8 text-red-500",
};
