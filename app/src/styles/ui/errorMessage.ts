/**
 * ErrorMessage component styles
 */

export const errorMessageStyles = {
  container: [
    "rounded-xl overflow-hidden",
    "bg-red-50 dark:bg-red-950/50",
    "border border-red-200 dark:border-red-900",
  ].join(" "),
  content: "px-4 py-3 flex items-start gap-3",
  iconWrapper: "shrink-0 mt-0.5",
  icon: "w-5 h-5 text-red-500",
  textContent: "flex-1 min-w-0",
  message: "text-sm font-medium text-red-800 dark:text-red-200",
  code: "text-xs text-red-600 dark:text-red-400 mt-0.5",
  dismissBtn: [
    "shrink-0 p-1 transition-colors",
    "text-red-400 hover:text-red-600 dark:hover:text-red-300",
  ].join(" "),
  retrySection: [
    "px-4 py-2",
    "bg-red-100/50 dark:bg-red-900/30",
    "border-t border-red-200 dark:border-red-900",
  ].join(" "),
  retryBtn: [
    "text-sm font-medium flex items-center gap-1.5",
    "text-red-700 dark:text-red-300",
    "hover:text-red-800 dark:hover:text-red-200",
    "disabled:opacity-50 disabled:cursor-not-allowed",
  ].join(" "),
};
