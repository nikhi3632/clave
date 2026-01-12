/**
 * Shared styles used across multiple components
 */

// Modal backdrop and container
export const modalStyles = {
  overlay: "fixed inset-0 z-[100] flex items-center justify-center",
  backdrop: "absolute inset-0 bg-black/50 backdrop-blur-sm",
  container: [
    "relative rounded-xl shadow-2xl overflow-hidden",
    "bg-white dark:bg-zinc-900",
  ].join(" "),
  header: [
    "flex items-center justify-between px-6 py-4",
    "border-b border-slate-200 dark:border-zinc-800",
  ].join(" "),
  title: "text-lg font-semibold text-slate-900 dark:text-zinc-100",
  closeBtn: [
    "p-2 rounded-lg transition-colors",
    "text-slate-400 hover:text-slate-600",
    "dark:hover:text-zinc-300",
    "hover:bg-slate-100 dark:hover:bg-zinc-800",
  ].join(" "),
  content: "p-6",
};

// Common text styles
export const textStyles = {
  heading: "font-semibold text-slate-900 dark:text-zinc-100",
  subheading: "text-sm font-medium text-slate-900 dark:text-zinc-100",
  body: "text-sm text-slate-600 dark:text-zinc-400",
  muted: "text-xs text-slate-400 dark:text-zinc-500",
  error: "text-red-500",
};

// Common layout styles
export const layoutStyles = {
  centered: "flex items-center justify-center",
  spaceBetween: "flex items-center justify-between",
  stack: "flex flex-col",
  row: "flex items-center",
};

// Table styles (shared between TableView and DrillDownModal)
export const tableStyles = {
  container: "overflow-x-auto",
  table: "min-w-full",
  thead: "bg-slate-50 dark:bg-zinc-800 sticky top-0",
  th: [
    "px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider",
    "text-slate-600 dark:text-zinc-400",
    "border-b border-slate-200 dark:border-zinc-700",
  ].join(" "),
  thRight: [
    "px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider",
    "text-slate-600 dark:text-zinc-400",
    "border-b border-slate-200 dark:border-zinc-700",
  ].join(" "),
  tbody: "divide-y divide-slate-100 dark:divide-zinc-800",
  tr: "hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors",
  trClickable: "hover:bg-slate-50 dark:hover:bg-zinc-800/50 transition-colors cursor-pointer",
  td: "px-4 py-3 text-sm text-slate-700 dark:text-zinc-300 whitespace-nowrap",
  tdMuted: "px-4 py-3 text-sm text-slate-600 dark:text-zinc-400 whitespace-nowrap",
  tdBold: "px-4 py-3 text-sm text-slate-900 dark:text-zinc-100 font-medium whitespace-nowrap",
  tdRight: "px-4 py-3 text-sm text-slate-600 dark:text-zinc-400 text-right whitespace-nowrap",
  tdRightBold: "px-4 py-3 text-sm text-slate-900 dark:text-zinc-100 font-medium text-right whitespace-nowrap",
};

// Badge/tag styles
export const badgeStyles = {
  default: [
    "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium",
    "bg-slate-100 dark:bg-zinc-800",
    "text-slate-700 dark:text-zinc-300",
  ].join(" "),
  small: [
    "px-1.5 py-0.5 rounded text-xs",
    "bg-slate-200 dark:bg-zinc-700",
  ].join(" "),
};

// Loading spinner
export const spinnerStyles = {
  container: "flex items-center justify-center py-12",
  spinner: "animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500",
};

// Stat card (used in DataQualityModal)
export const statCardStyles = {
  container: "text-center p-4 bg-slate-50 dark:bg-zinc-800 rounded-lg",
  value: "text-2xl font-bold text-slate-900 dark:text-zinc-100",
  label: "text-sm text-slate-500 dark:text-zinc-400",
};
