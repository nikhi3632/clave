/**
 * Base chart styles shared across all chart types
 */

export const chartBaseStyles = {
  // Responsive container
  container: "w-full h-[300px]",

  // Centered container for metric/info cards
  centeredContainer: "flex flex-col items-center justify-center h-[200px]",

  // Text styles
  metricValue: [
    "text-5xl font-bold",
    "bg-gradient-to-r from-blue-600 to-blue-400",
    "bg-clip-text text-transparent",
  ].join(" "),
  metricLabel: "text-sm text-slate-500 dark:text-zinc-400 mt-2 capitalize",
  noDataValue: "text-5xl font-bold text-slate-300 dark:text-zinc-600",
  noDataLabel: "text-sm text-slate-500 dark:text-zinc-400 mt-2",

  // Cell hover effect (for clickable charts)
  cellHover: "hover:opacity-80",
};

// Recharts tooltip content style (inline styles required by Recharts)
export const getTooltipStyle = (colors: {
  tooltipBg: string;
  tooltipBorder: string;
}) => ({
  backgroundColor: colors.tooltipBg,
  border: `1px solid ${colors.tooltipBorder}`,
  borderRadius: "8px",
  boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
});

// Legend formatter style
export const getLegendStyle = (colors: { legendText: string }) => ({
  color: colors.legendText,
  fontSize: "14px",
  textTransform: "capitalize" as const,
});
