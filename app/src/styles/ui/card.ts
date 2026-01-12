/**
 * Card component styles
 */

export const cardStyles = {
  base: [
    "rounded-2xl shadow-sm",
    "bg-white dark:bg-zinc-900",
    "border border-slate-200 dark:border-zinc-800",
  ].join(" "),
  header: [
    "px-5 py-4",
    "border-b border-slate-100 dark:border-zinc-800",
  ].join(" "),
  content: "p-5",
  footer: [
    "px-5 py-4",
    "bg-slate-50 dark:bg-zinc-800/50",
    "border-t border-slate-100 dark:border-zinc-800",
  ].join(" "),
};
