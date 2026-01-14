import { ValueFormat } from "@/types";

// Modern color palette for charts
export const CHART_COLORS = [
  "#3b82f6",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#8b5cf6",
  "#ec4899",
  "#06b6d4",
  "#84cc16",
];

// Theme-aware colors
export function getChartColors(isDark: boolean) {
  return {
    grid: isDark ? "#3f3f46" : "#e2e8f0",
    tick: isDark ? "#a1a1aa" : "#64748b",
    axis: isDark ? "#3f3f46" : "#e2e8f0",
    tooltipBg: isDark ? "#18181b" : "#fff",
    tooltipBorder: isDark ? "#3f3f46" : "#e2e8f0",
    tooltipLabel: isDark ? "#fafafa" : "#334155",
    legendText: isDark ? "#a1a1aa" : "#64748b",
    cursor: isDark ? "#27272a" : "#f1f5f9",
    labelText: isDark ? "#71717a" : "#94a3b8",
    dotStroke: isDark ? "#18181b" : "#fff",
  };
}

// Format value based on type
export function createFormatter(format?: ValueFormat) {
  return (value: number | string | Array<number | string> | undefined): string => {
    if (value === undefined || value === null) return "";
    if (typeof value !== "number") return String(value);

    switch (format) {
      case "currency": {
        const dollars = value / 100;
        return `$${dollars.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      }
      case "percent":
        return `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })}%`;
      case "number":
      default:
        return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
  };
}

// Format Y-axis ticks (shorter format)
export function createTickFormatter(format?: ValueFormat) {
  return (value: number): string => {
    switch (format) {
      case "currency": {
        const dollars = value / 100;
        if (dollars >= 1000000) return `$${(dollars / 1000000).toFixed(1)}M`;
        if (dollars >= 1000) return `$${(dollars / 1000).toFixed(1)}K`;
        return `$${dollars.toFixed(0)}`;
      }
      case "percent":
        return `${value}%`;
      case "number":
      default:
        if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
        if (value >= 1000) return `${(value / 1000).toFixed(1)}K`;
        return value.toLocaleString();
    }
  };
}

// Get unit label for Y-axis
export function getUnitLabel(format?: ValueFormat, columnName?: string): string {
  if (format === "currency") return "(USD)";
  if (format === "percent") return "(%)";
  if (columnName) {
    const lower = columnName.toLowerCase();
    if (lower.includes("order") || lower.includes("count")) return "(orders)";
    if (lower.includes("unit") || lower.includes("sold")) return "(units)";
  }
  return "";
}
