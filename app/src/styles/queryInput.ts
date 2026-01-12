/**
 * QueryInput component styles
 */

export const queryInputStyles = {
  card: "p-6",
  form: "space-y-4",

  // Input wrapper
  inputWrapper: "relative",
  inputIcon: "absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none",
  input: [
    "w-full pl-12 pr-32 py-4 rounded-xl transition-all",
    "bg-slate-50 dark:bg-zinc-800",
    "border border-slate-200 dark:border-zinc-700",
    "text-slate-900 dark:text-zinc-100",
    "placeholder-slate-400 dark:placeholder-zinc-500",
    "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent",
  ].join(" "),

  // Submit button
  buttonWrapper: "absolute inset-y-0 right-0 flex items-center pr-2",
  submitBtn: [
    "px-5 py-2.5 rounded-lg font-medium shadow-sm",
    "flex items-center gap-2 transition-all",
    "bg-blue-500 text-white hover:bg-blue-600",
    "disabled:bg-slate-300 dark:disabled:bg-zinc-700 disabled:cursor-not-allowed",
  ].join(" "),

  // Example queries
  examplesWrapper: "flex items-center gap-2 flex-wrap",
  examplesLabel: "text-xs font-medium text-slate-400 dark:text-zinc-500 uppercase tracking-wide",
  exampleBtn: [
    "inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full transition-colors",
    "bg-slate-100 dark:bg-zinc-800",
    "text-slate-600 dark:text-zinc-400",
    "hover:bg-blue-100 dark:hover:bg-blue-900/50",
    "hover:text-blue-700 dark:hover:text-blue-300",
  ].join(" "),
};
