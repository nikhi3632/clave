"use client";

import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { ValueFormat, DrillDownFilters, DrillDownConfig } from "@/types";
import { CHART_COLORS, getChartColors, createFormatter } from "./chartTheme";

interface PieChartViewProps {
  data: Record<string, unknown>[];
  dataKey: string;
  nameKey: string;
  valueFormat?: ValueFormat;
  isDark: boolean;
  drillDown?: DrillDownConfig;
  onDataClick?: (filters: DrillDownFilters) => void;
}

export function PieChartView({
  data,
  dataKey,
  nameKey,
  valueFormat,
  isDark,
  drillDown,
  onDataClick,
}: PieChartViewProps) {
  const colors = getChartColors(isDark);
  const formatValue = createFormatter(valueFormat);

  // Filter out null/undefined values from pie chart data
  const filteredData = data.filter((item) => {
    const value = item[nameKey];
    return value !== null && value !== undefined && value !== "";
  });

  // Check if drill-down is enabled
  const isDrillDownEnabled = drillDown?.enabled && onDataClick;

  // Build drill-down filters from pie segment using LLM-provided config
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleSegmentClick = (entry: any) => {
    if (!isDrillDownEnabled || !drillDown?.type || !drillDown?.column) return;

    const value = entry[drillDown.column] || entry?.payload?.[drillDown.column] || entry?.name;
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
      <PieChart>
        <Pie
          data={filteredData}
          dataKey={dataKey}
          nameKey={nameKey}
          cx="50%"
          cy="50%"
          innerRadius={60}
          outerRadius={100}
          paddingAngle={2}
          label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}
          labelLine={{ stroke: colors.legendText, strokeWidth: 1 }}
          onClick={(entry) => handleSegmentClick(entry)}
          style={{ cursor: isDrillDownEnabled ? "pointer" : "default" }}
        >
          {filteredData.map((_, index) => (
            <Cell
              key={`cell-${index}`}
              fill={CHART_COLORS[index % CHART_COLORS.length]}
              className={isDrillDownEnabled ? "hover:opacity-80" : ""}
            />
          ))}
        </Pie>
        <Tooltip
          formatter={(value) => [formatValue(value as number), dataKey.replace(/_/g, " ")]}
          contentStyle={{
            backgroundColor: colors.tooltipBg,
            border: `1px solid ${colors.tooltipBorder}`,
            borderRadius: "8px",
            boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
          }}
          labelStyle={{ color: colors.tooltipLabel }}
          itemStyle={{ color: colors.tooltipLabel }}
        />
        <Legend
          verticalAlign="bottom"
          height={36}
          iconType="circle"
          formatter={(value) => (
            <span style={{ color: colors.legendText, fontSize: "14px" }}>{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
