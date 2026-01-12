"use client";

import { ChartProps } from "@/types";
import { useTheme } from "@/hooks/useTheme";
import { BarChartView } from "./BarChartView";
import { LineChartView } from "./LineChartView";
import { PieChartView } from "./PieChartView";
import { TableView } from "./TableView";
import { MetricView } from "./MetricView";
import { InfoCard } from "./InfoCard";
import { NoData } from "./NoData";

export function ChartWrapper({
  type,
  data,
  xAxis,
  yAxis,
  dataKey,
  nameKey,
  valueFormat,
  summary,
  onDataClick,
}: ChartProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  // Info card - for welcome messages and non-analytics queries
  if (type === "info") {
    return <InfoCard summary={summary} />;
  }

  // No data state
  if (!data || data.length === 0) {
    return <NoData />;
  }

  // Metric - single big number
  if (type === "metric") {
    return <MetricView data={data} valueFormat={valueFormat} />;
  }

  // Table
  if (type === "table") {
    return <TableView data={data} valueFormat={valueFormat} onDataClick={onDataClick} />;
  }

  // Helper to safely get keys from first data row
  const firstRow = data[0] || {};
  const keys = Object.keys(firstRow);
  const findNumericKey = () => keys.find((k) => typeof firstRow[k] === "number") || keys[0] || "value";
  const findStringKey = () => keys.find((k) => typeof firstRow[k] === "string") || keys[0] || "name";

  // Pie Chart
  if (type === "pie") {
    const key = dataKey || findNumericKey();
    const name = nameKey || findStringKey();
    return (
      <PieChartView
        data={data}
        dataKey={key}
        nameKey={name}
        valueFormat={valueFormat}
        isDark={isDark}
        onDataClick={onDataClick}
      />
    );
  }

  // Line Chart
  if (type === "line") {
    const x = xAxis || keys[0] || "x";
    const y = yAxis || findNumericKey();
    return (
      <LineChartView
        data={data}
        xAxis={x}
        yAxis={y}
        valueFormat={valueFormat}
        isDark={isDark}
        onDataClick={onDataClick}
      />
    );
  }

  // Bar Chart (default)
  const x = xAxis || keys[0] || "x";
  const y = yAxis || findNumericKey();
  return (
    <BarChartView
      data={data}
      xAxis={x}
      yAxis={y}
      valueFormat={valueFormat}
      isDark={isDark}
      onDataClick={onDataClick}
    />
  );
}
