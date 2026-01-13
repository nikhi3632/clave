"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { ValueFormat, DrillDownFilters, DrillDownConfig } from "@/types";
import {
  getChartColors,
  createFormatter,
  createTickFormatter,
  getUnitLabel,
} from "./chartTheme";

interface BarChartViewProps {
  data: Record<string, unknown>[];
  xAxis: string;
  yAxis: string;
  valueFormat?: ValueFormat;
  isDark: boolean;
  drillDown?: DrillDownConfig;
  onDataClick?: (filters: DrillDownFilters) => void;
}

export function BarChartView({
  data,
  xAxis,
  yAxis,
  valueFormat,
  isDark,
  drillDown,
  onDataClick,
}: BarChartViewProps) {
  const colors = getChartColors(isDark);
  const formatValue = createFormatter(valueFormat);
  const formatTick = createTickFormatter(valueFormat);
  const unitLabel = getUnitLabel(valueFormat, yAxis);

  // Check if drill-down is enabled
  const isDrillDownEnabled = drillDown?.enabled && onDataClick;

  // Build drill-down filters from data row using LLM-provided config
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleBarClick = (entry: any) => {
    if (!isDrillDownEnabled || !drillDown?.type || !drillDown?.column) return;

    // Get the actual data - recharts wraps it in payload sometimes
    const rowData = entry?.payload || entry;
    const value = rowData?.[drillDown.column];

    if (value === null || value === undefined || value === "") return;

    const filters: DrillDownFilters = {};
    const strValue = String(value);

    // Use the LLM-specified type to set the correct filter
    switch (drillDown.type) {
      case "product":
        filters.product = strValue;
        break;
      case "location":
        filters.location = strValue;
        break;
      case "date":
        filters.date = strValue;
        break;
      case "source":
        filters.source = strValue;
        break;
      case "channel":
        filters.channel = strValue;
        break;
      case "category":
        filters.category = strValue;
        break;
    }

    if (Object.keys(filters).length > 0) {
      onDataClick(filters);
    }
  };

  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
        <XAxis
          dataKey={xAxis}
          tick={{ fontSize: 12, fill: colors.tick }}
          tickLine={{ stroke: colors.axis }}
          axisLine={{ stroke: colors.axis }}
        />
        <YAxis
          tick={{ fontSize: 12, fill: colors.tick }}
          tickLine={{ stroke: colors.axis }}
          axisLine={{ stroke: colors.axis }}
          tickFormatter={formatTick}
          label={
            unitLabel
              ? {
                  value: unitLabel,
                  angle: -90,
                  position: "insideLeft",
                  style: { fontSize: 11, fill: colors.labelText },
                }
              : undefined
          }
        />
        <Tooltip
          formatter={(value) => [formatValue(value as number), yAxis.replace(/_/g, " ")]}
          contentStyle={{
            backgroundColor: colors.tooltipBg,
            border: `1px solid ${colors.tooltipBorder}`,
            borderRadius: "8px",
            boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
          }}
          labelStyle={{ fontWeight: 600, color: colors.tooltipLabel }}
          itemStyle={{ color: colors.tooltipLabel }}
          cursor={{ fill: colors.cursor }}
        />
        <Legend
          verticalAlign="top"
          height={36}
          formatter={(value) => (
            <span style={{ color: colors.legendText, fontSize: "14px", textTransform: "capitalize" }}>
              {value.replace(/_/g, " ")}
            </span>
          )}
        />
        <Bar
          dataKey={yAxis}
          fill="#3b82f6"
          radius={[4, 4, 0, 0]}
          maxBarSize={60}
          onClick={(entry) => handleBarClick(entry)}
          style={{ cursor: isDrillDownEnabled ? "pointer" : "default" }}
        >
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} className={isDrillDownEnabled ? "hover:opacity-80" : ""} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
