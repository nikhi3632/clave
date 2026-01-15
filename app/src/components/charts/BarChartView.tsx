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
  chartMargins,
  chartBaseStyles,
  barStyles,
  getTooltipContentStyle,
  getTooltipLabelStyle,
  getTooltipItemStyle,
  getAxisTickStyle,
  getAxisLineStyle,
  getYAxisLabelStyle,
  getLegendTextStyle,
  getCursorStyle,
  getClickableStyle,
} from "@/styles/charts";
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
  const isDrillDownEnabled = drillDown?.enabled && onDataClick;

  const handleBarClick = (entry: Record<string, unknown>) => {
    if (!isDrillDownEnabled || !drillDown?.type || !drillDown?.column) return;

    const rowData = (entry?.payload as Record<string, unknown>) || entry;
    const value = rowData?.[drillDown.column];
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
    <ResponsiveContainer width="100%" height={350}>
      <BarChart data={data} margin={chartMargins}>
        <CartesianGrid strokeDasharray="3 3" stroke={colors.grid} vertical={false} />
        <XAxis
          dataKey={xAxis}
          tick={getAxisTickStyle(colors)}
          tickLine={getAxisLineStyle(colors)}
          axisLine={getAxisLineStyle(colors)}
          interval={0}
          angle={-45}
          textAnchor="end"
          height={80}
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
          cursor={getCursorStyle(colors)}
        />
        <Legend
          verticalAlign="top"
          height={36}
          formatter={(value) => (
            <span style={getLegendTextStyle(colors)}>{value.replace(/_cents$/i, "").replace(/_/g, " ")}</span>
          )}
        />
        <Bar
          dataKey={yAxis}
          fill={barStyles.fill}
          radius={barStyles.radius}
          maxBarSize={barStyles.maxBarSize}
          onClick={(entry) => handleBarClick(entry as unknown as Record<string, unknown>)}
          style={getClickableStyle(!!isDrillDownEnabled)}
        >
          {data.map((_, index) => (
            <Cell
              key={`cell-${index}`}
              className={isDrillDownEnabled ? chartBaseStyles.cellHover : ""}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
