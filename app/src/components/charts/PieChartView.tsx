"use client";

import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { ValueFormat, DrillDownFilters } from "@/types";
import { CHART_COLORS, getChartColors, createFormatter } from "./chartTheme";

interface PieChartViewProps {
  data: Record<string, unknown>[];
  dataKey: string;
  nameKey: string;
  valueFormat?: ValueFormat;
  isDark: boolean;
  onDataClick?: (filters: DrillDownFilters) => void;
}

export function PieChartView({
  data,
  dataKey,
  nameKey,
  valueFormat,
  isDark,
  onDataClick,
}: PieChartViewProps) {
  const colors = getChartColors(isDark);
  const formatValue = createFormatter(valueFormat);

  // Filter out null/undefined values from pie chart data
  const filteredData = data.filter((item) => {
    const value = item[nameKey];
    return value !== null && value !== undefined && value !== "";
  });

  // Build drill-down filters from pie segment
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleSegmentClick = (entry: any) => {
    if (!onDataClick) return;
    const filters: DrillDownFilters = {};
    const nameValue = String(entry[nameKey] || entry?.payload?.[nameKey] || entry?.name || "");

    const nameLower = nameKey.toLowerCase();
    if (nameLower.includes("product") || nameLower === "name") {
      filters.product = nameValue;
    } else if (nameLower.includes("location")) {
      filters.location = nameValue;
    } else if (nameLower.includes("source")) {
      filters.source = nameValue;
    } else if (nameLower.includes("channel")) {
      filters.channel = nameValue;
    } else if (nameLower.includes("payment")) {
      filters.payment_type = nameValue;
    } else if (nameLower.includes("category")) {
      filters.category = nameValue;
    } else {
      filters.product = nameValue;
    }

    onDataClick(filters);
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
          style={{ cursor: onDataClick ? "pointer" : "default" }}
        >
          {filteredData.map((_, index) => (
            <Cell
              key={`cell-${index}`}
              fill={CHART_COLORS[index % CHART_COLORS.length]}
              className={onDataClick ? "hover:opacity-80" : ""}
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
