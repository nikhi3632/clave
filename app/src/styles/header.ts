/**
 * Header component styles
 */

export const headerStyles = {
  header: [
    "sticky top-0 z-50",
    "bg-white/80 dark:bg-zinc-900/80 backdrop-blur-sm",
    "border-b border-slate-200 dark:border-zinc-800",
  ].join(" "),

  container: "max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8",
  content: "flex items-center justify-between",

  // Logo section
  logoSection: "flex items-center gap-3",
  logoIcon: [
    "w-10 h-10 rounded-xl flex items-center justify-center",
    "bg-gradient-to-br from-blue-500 to-blue-600",
    "shadow-lg shadow-blue-500/25",
  ].join(" "),
  title: "text-xl font-semibold text-slate-900 dark:text-zinc-100",
  subtitle: "text-sm text-slate-500 dark:text-zinc-400",

  // Actions section
  actions: "flex items-center gap-2",
  iconBtn: [
    "p-2 rounded-lg transition-colors",
    "text-slate-500 dark:text-zinc-400",
    "hover:text-slate-700 dark:hover:text-zinc-200",
    "hover:bg-slate-100 dark:hover:bg-zinc-800",
  ].join(" "),
};
