/**
 * Base chart styles shared across all Recharts components
 */

import { CSSProperties } from "react";

// Chart colors type from chartTheme
type ChartColors = {
  grid: string;
  tick: string;
  axis: string;
  tooltipBg: string;
  tooltipBorder: string;
  tooltipLabel: string;
  legendText: string;
  cursor: string;
  labelText: string;
  dotStroke: string;
};

// Primary chart color
export const PRIMARY_COLOR = "#3b82f6";

// Tailwind class-based styles
export const chartBaseStyles = {
  container: "w-full h-[300px]",
  centeredContainer: "flex flex-col items-center justify-center h-[200px]",
  metricValue: [
    "text-5xl font-bold",
    "bg-gradient-to-r from-blue-600 to-blue-400",
    "bg-clip-text text-transparent",
  ].join(" "),
  metricLabel: "text-sm text-slate-500 dark:text-zinc-400 mt-2 capitalize",
  noDataValue: "text-5xl font-bold text-slate-300 dark:text-zinc-600",
  noDataLabel: "text-sm text-slate-500 dark:text-zinc-400 mt-2",
  cellHover: "hover:opacity-80",
};

// Chart margins
export const chartMargins = { top: 5, right: 20, left: 10, bottom: 5 };

// Tooltip styles
export const getTooltipContentStyle = (colors: ChartColors): CSSProperties => ({
  backgroundColor: colors.tooltipBg,
  border: `1px solid ${colors.tooltipBorder}`,
  borderRadius: "8px",
  boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
});

export const getTooltipLabelStyle = (colors: ChartColors): CSSProperties => ({
  fontWeight: 600,
  color: colors.tooltipLabel,
});

export const getTooltipItemStyle = (colors: ChartColors): CSSProperties => ({
  color: colors.tooltipLabel,
});

// Axis styles
export const getAxisTickStyle = (colors: ChartColors) => ({
  fontSize: 12,
  fill: colors.tick,
});

export const getAxisLineStyle = (colors: ChartColors) => ({
  stroke: colors.axis,
});

export const getYAxisLabelStyle = (colors: ChartColors): CSSProperties => ({
  fontSize: 11,
  fill: colors.labelText,
});

// Legend styles
export const getLegendTextStyle = (
  colors: ChartColors,
  capitalize = true
): CSSProperties => ({
  color: colors.legendText,
  fontSize: "14px",
  ...(capitalize && { textTransform: "capitalize" }),
});

// Bar chart styles
export const barStyles = {
  fill: PRIMARY_COLOR,
  radius: [4, 4, 0, 0] as [number, number, number, number],
  maxBarSize: 60,
};

// Line chart styles
export const lineStyles = {
  stroke: PRIMARY_COLOR,
  strokeWidth: 2.5,
};

export const getDotStyle = (colors: ChartColors, isClickable: boolean) => ({
  r: 4,
  fill: PRIMARY_COLOR,
  strokeWidth: 2,
  stroke: colors.dotStroke,
  cursor: isClickable ? "pointer" : "default",
});

export const getActiveDotStyle = (colors: ChartColors, isClickable: boolean) => ({
  r: 6,
  fill: PRIMARY_COLOR,
  strokeWidth: 2,
  stroke: colors.dotStroke,
  cursor: isClickable ? "pointer" : "default",
});

// Pie chart styles
export const pieStyles = {
  innerRadius: 60,
  outerRadius: 100,
  paddingAngle: 2,
};

export const getLabelLineStyle = (colors: ChartColors) => ({
  stroke: colors.legendText,
  strokeWidth: 1,
});

// Cursor style for tooltips
export const getCursorStyle = (colors: ChartColors) => ({
  fill: colors.cursor,
});

// Clickable element style
export const getClickableStyle = (isClickable: boolean): CSSProperties => ({
  cursor: isClickable ? "pointer" : "default",
});
