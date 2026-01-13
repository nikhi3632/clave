"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { ValueFormat, DrillDownFilters, DrillDownConfig } from "@/types";
import {
  getChartColors,
  createFormatter,
  createTickFormatter,
  getUnitLabel,
} from "./chartTheme";

interface LineChartViewProps {
  data: Record<string, unknown>[];
  xAxis: string;
  yAxis: string;
  valueFormat?: ValueFormat;
  isDark: boolean;
  drillDown?: DrillDownConfig;
  onDataClick?: (filters: DrillDownFilters) => void;
}

export function LineChartView({
  data,
  xAxis,
  yAxis,
  valueFormat,
  isDark,
  drillDown,
  onDataClick,
}: LineChartViewProps) {
  const colors = getChartColors(isDark);
  const formatValue = createFormatter(valueFormat);
  const formatTick = createTickFormatter(valueFormat);
  const unitLabel = getUnitLabel(valueFormat, yAxis);

  // Check if drill-down is enabled
  const isDrillDownEnabled = drillDown?.enabled && onDataClick;

  // Build drill-down filters from data point using LLM-provided config
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleDotClick = (entry: any) => {
    if (!isDrillDownEnabled || !drillDown?.type || !drillDown?.column) return;

    const value = entry[drillDown.column] || entry?.payload?.[drillDown.column];
    if (value === null || value === undefined || value === "") return;

    const filters: DrillDownFilters = {};
    const strValue = String(value);

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
      <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
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
        <Line
          type="monotone"
          dataKey={yAxis}
          stroke="#3b82f6"
          strokeWidth={2.5}
          dot={{
            r: 4,
            fill: "#3b82f6",
            strokeWidth: 2,
            stroke: colors.dotStroke,
            cursor: isDrillDownEnabled ? "pointer" : "default",
          }}
          activeDot={{
            r: 6,
            fill: "#3b82f6",
            strokeWidth: 2,
            stroke: colors.dotStroke,
            cursor: isDrillDownEnabled ? "pointer" : "default",
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            onClick: (_: any, payload: any) => handleDotClick(payload?.payload || payload),
          }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
