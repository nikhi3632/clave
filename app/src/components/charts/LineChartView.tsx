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
  chartMargins,
  lineStyles,
  getTooltipContentStyle,
  getTooltipLabelStyle,
  getTooltipItemStyle,
  getAxisTickStyle,
  getAxisLineStyle,
  getYAxisLabelStyle,
  getLegendTextStyle,
  getDotStyle,
  getActiveDotStyle,
} from "@/styles/charts";
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
  const isDrillDownEnabled = drillDown?.enabled && onDataClick;

  const handleDotClick = (entry: Record<string, unknown>) => {
    if (!isDrillDownEnabled || !drillDown?.type || !drillDown?.column) return;

    const payload = entry?.payload as Record<string, unknown> | undefined;
    const value = entry[drillDown.column] || payload?.[drillDown.column];
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
      <LineChart data={data} margin={chartMargins}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} />
        <XAxis
          dataKey={xAxis}
          tick={getAxisTickStyle(colors)}
          tickLine={getAxisLineStyle(colors)}
          axisLine={getAxisLineStyle(colors)}
        />
        <YAxis
          tick={getAxisTickStyle(colors)}
          tickLine={getAxisLineStyle(colors)}
          axisLine={getAxisLineStyle(colors)}
          tickFormatter={formatTick}
          label={
            unitLabel
              ? {
                  value: unitLabel,
                  angle: -90,
                  position: "insideLeft",
                  style: getYAxisLabelStyle(colors),
                }
              : undefined
          }
        />
        <Tooltip
          formatter={(value) => [formatValue(value as number), yAxis.replace(/_cents$/i, "").replace(/_/g, " ")]}
          contentStyle={getTooltipContentStyle(colors)}
          labelStyle={getTooltipLabelStyle(colors)}
          itemStyle={getTooltipItemStyle(colors)}
        />
        <Legend
          verticalAlign="top"
          height={36}
          formatter={(value) => (
            <span style={getLegendTextStyle(colors)}>{value.replace(/_cents$/i, "").replace(/_/g, " ")}</span>
          )}
        />
        <Line
          type="monotone"
          dataKey={yAxis}
          stroke={lineStyles.stroke}
          strokeWidth={lineStyles.strokeWidth}
          dot={getDotStyle(colors, !!isDrillDownEnabled)}
          activeDot={{
            ...getActiveDotStyle(colors, !!isDrillDownEnabled),
            onClick: (_event, payload) => {
              const p = payload as unknown as Record<string, unknown>;
              const data = (p?.payload as Record<string, unknown>) || p;
              handleDotClick(data);
            },
          }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
