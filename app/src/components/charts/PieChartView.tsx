"use client";

import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { ValueFormat, DrillDownFilters, DrillDownConfig } from "@/types";
import {
  chartBaseStyles,
  pieStyles,
  getTooltipContentStyle,
  getTooltipItemStyle,
  getLegendTextStyle,
  getLabelLineStyle,
  getClickableStyle,
} from "@/styles/charts";
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

  const filteredData = data.filter((item) => {
    const value = item[nameKey];
    return value !== null && value !== undefined && value !== "";
  });

  const isDrillDownEnabled = drillDown?.enabled && onDataClick;

  const handleSegmentClick = (entry: Record<string, unknown>) => {
    if (!isDrillDownEnabled || !drillDown?.type || !drillDown?.column) return;

    const payload = entry?.payload as Record<string, unknown> | undefined;
    const value = entry[drillDown.column] || payload?.[drillDown.column] || entry?.name;
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
      case "payment_type":
        filters.payment_type = strValue;
        break;
    }

    // Include summary SQL for 100% accurate drill-down
    if (drillDown.summarySQL) {
      filters.summarySQL = drillDown.summarySQL;
      filters.summaryLabel = drillDown.summaryLabel;
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
          innerRadius={pieStyles.innerRadius}
          outerRadius={pieStyles.outerRadius}
          paddingAngle={pieStyles.paddingAngle}
          label={({ name, percent }) => `${name} (${((percent ?? 0) * 100).toFixed(0)}%)`}
          labelLine={getLabelLineStyle(colors)}
          onClick={(entry) => handleSegmentClick(entry as unknown as Record<string, unknown>)}
          style={getClickableStyle(!!isDrillDownEnabled)}
        >
          {filteredData.map((_, index) => (
            <Cell
              key={`cell-${index}`}
              fill={CHART_COLORS[index % CHART_COLORS.length]}
              className={isDrillDownEnabled ? chartBaseStyles.cellHover : ""}
            />
          ))}
        </Pie>
        <Tooltip
          formatter={(value) => [formatValue(value as number), dataKey.replace(/_cents$/i, "").replace(/_/g, " ")]}
          contentStyle={getTooltipContentStyle(colors)}
          labelStyle={getTooltipItemStyle(colors)}
          itemStyle={getTooltipItemStyle(colors)}
        />
        <Legend
          verticalAlign="bottom"
          height={36}
          iconType="circle"
          formatter={(value) => (
            <span style={getLegendTextStyle(colors, false)}>{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
