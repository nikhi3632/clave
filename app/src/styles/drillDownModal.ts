/**
 * DrillDownModal component styles
 */

import { modalStyles, tableStyles, spinnerStyles, badgeStyles } from "./shared";

export const drillDownModalStyles = {
  // Base modal styles
  ...modalStyles,

  // Override container for drill-down specific sizing
  container: [
    modalStyles.container,
    "w-full max-w-4xl max-h-[90vh] mx-2 sm:mx-4 flex flex-col",
  ].join(" "),

  // Header
  header: [
    "flex items-center justify-between px-4 sm:px-6 py-4",
    "border-b border-slate-200 dark:border-zinc-800",
  ].join(" "),
  headerContent: "min-w-0 flex-1 mr-4",
  title: "text-base sm:text-lg font-semibold text-slate-900 dark:text-zinc-100 truncate",
  subtitle: "text-sm text-slate-500 dark:text-zinc-400",
  closeBtn: [
    "shrink-0 p-2 rounded-lg transition-colors",
    "text-slate-400 hover:text-slate-600",
    "dark:hover:text-zinc-300",
    "hover:bg-slate-100 dark:hover:bg-zinc-800",
  ].join(" "),

  // Content
  content: "flex-1 overflow-auto p-4 sm:p-6",

  // States
  loading: spinnerStyles,
  error: {
    container: "text-center py-12",
    message: "text-red-500 mb-2",
    hint: "text-sm text-slate-500 dark:text-zinc-400",
  },
  empty: "text-center py-12 text-slate-500 dark:text-zinc-400",

  // Mobile card layout
  mobileContainer: "sm:hidden space-y-3",
  mobileCard: "bg-slate-50 dark:bg-zinc-800 rounded-lg p-4",
  mobileCardHeader: "flex justify-between items-start mb-2",
  mobileCardTitle: "font-medium text-slate-900 dark:text-zinc-100",
  mobileCardMeta: "flex flex-wrap gap-2 text-xs text-slate-500 dark:text-zinc-400",
  mobileCardFooter: "flex justify-between mt-2 text-sm text-slate-600 dark:text-zinc-400",
  badge: badgeStyles.small,

  // Desktop table layout
  desktopContainer: "hidden sm:block overflow-x-auto",
  table: tableStyles,

  // Footer
  footer: [
    "px-4 sm:px-6 py-3",
    "border-t border-slate-200 dark:border-zinc-800",
    "bg-slate-50 dark:bg-zinc-800/50",
  ].join(" "),
  footerContent: "flex justify-between text-sm",
  footerCount: "text-slate-500 dark:text-zinc-400",
  footerTotal: "font-medium text-slate-900 dark:text-zinc-100",
};
