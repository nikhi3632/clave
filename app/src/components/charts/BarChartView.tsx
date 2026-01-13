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
import { ValueFormat, DrillDownFilters } from "@/types";
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
  onDataClick?: (filters: DrillDownFilters) => void;
}

export function BarChartView({
  data,
  xAxis,
  yAxis,
  valueFormat,
  isDark,
  onDataClick,
}: BarChartViewProps) {
  const colors = getChartColors(isDark);
  const formatValue = createFormatter(valueFormat);
  const formatTick = createTickFormatter(valueFormat);
  const unitLabel = getUnitLabel(valueFormat, yAxis);

  // Build drill-down filters from data row
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleBarClick = (entry: any) => {
    if (!onDataClick) return;

    // Get the actual data - recharts wraps it in payload sometimes
    const rowData = entry?.payload || entry;
    const filters: DrillDownFilters = {};

    // Try to extract filter values from the row data
    const product = rowData?.product || rowData?.name || rowData?.canonical_name || rowData?.[xAxis];
    const location = rowData?.location;
    const date = rowData?.date;
    const source = rowData?.source;
    const channel = rowData?.channel;
    const payment_type = rowData?.payment_type;
    const category = rowData?.category;

    // Detect which filter to use based on xAxis or available data
    const xLower = xAxis.toLowerCase();
    if (xLower.includes("product") || xLower === "name" || xLower === "canonical_name") {
      if (product) filters.product = String(product);
    } else if (xLower.includes("location")) {
      if (location) filters.location = String(location);
    } else if (xLower.includes("date") || xLower.includes("day")) {
      if (date) filters.date = String(date);
    } else if (xLower.includes("source")) {
      if (source) filters.source = String(source);
    } else if (xLower.includes("channel")) {
      if (channel) filters.channel = String(channel);
    } else if (xLower.includes("payment")) {
      if (payment_type) filters.payment_type = String(payment_type);
    } else if (xLower.includes("category")) {
      if (category) filters.category = String(category);
    } else if (product) {
      filters.product = String(product);
    }

    if (Object.keys(filters).length > 0 && Object.values(filters).some(v => v)) {
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
          style={{ cursor: onDataClick ? "pointer" : "default" }}
        >
          {data.map((_, index) => (
            <Cell key={`cell-${index}`} className={onDataClick ? "hover:opacity-80" : ""} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
