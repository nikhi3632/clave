/**
 * LoadingState component styles
 */

export const loadingStateStyles = {
  card: "p-8",
  content: "flex items-center justify-center gap-4",
  spinnerWrapper: "relative",
  spinnerBg: "w-12 h-12 rounded-full border-4 border-slate-200 dark:border-zinc-700",
  spinner: [
    "w-12 h-12 rounded-full border-4 border-blue-500 border-t-transparent",
    "animate-spin absolute top-0 left-0",
  ].join(" "),
  title: "font-medium text-slate-900 dark:text-zinc-100",
  description: "text-sm text-slate-500 dark:text-zinc-400",
};
