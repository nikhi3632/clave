/**
 * Widget component styles
 */

export const widgetStyles = {
  card: "overflow-hidden hover:shadow-md transition-shadow",

  // Header
  header: "flex justify-between items-start gap-4",
  headerContent: "flex items-start gap-3 min-w-0",
  iconWrapper: [
    "w-8 h-8 rounded-lg shrink-0 mt-0.5",
    "flex items-center justify-center",
    "bg-blue-50 dark:bg-blue-900/50",
    "text-blue-600 dark:text-blue-400",
  ].join(" "),
  title: "font-semibold text-slate-900 dark:text-zinc-100 truncate",
  subtitle: "text-xs text-slate-400 dark:text-zinc-500 truncate mt-0.5",

  // Remove button
  removeBtn: [
    "p-1.5 rounded-lg shrink-0 transition-colors",
    "text-slate-400 dark:text-zinc-500",
    "hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/50",
  ].join(" "),

  // Summary
  summary: "text-sm text-slate-600 dark:text-zinc-400 leading-relaxed",

  // Meta bar (bottom section)
  metaBar: "border-t border-slate-100 dark:border-zinc-800",
  metaContent: "px-5 py-2.5 flex items-center justify-between",
  metaText: "flex items-center gap-1.5 text-xs text-slate-400 dark:text-zinc-500",

  // SQL toggle
  sqlBtn: [
    "flex items-center gap-1 text-xs transition-colors",
    "text-slate-400 dark:text-zinc-500",
    "hover:text-slate-600 dark:hover:text-zinc-300",
  ].join(" "),
  sqlContainer: "px-5 pb-4",
  sqlPre: [
    "text-xs p-4 rounded-lg overflow-x-auto font-mono",
    "bg-slate-900 dark:bg-black",
    "text-slate-300 dark:text-zinc-400",
  ].join(" "),
};
