"use client";

import { ValueFormat } from "@/types";
import { createFormatter } from "./chartTheme";
import { metricViewStyles as styles } from "@/styles/charts/metric";

interface MetricViewProps {
  data: Record<string, unknown>[];
  valueFormat?: ValueFormat;
}

export function MetricView({ data, valueFormat }: MetricViewProps) {
  const firstRow = data[0];

  if (!firstRow) {
    return (
      <div className={styles.container}>
        <div className={styles.noDataValue}>--</div>
        <div className={styles.noDataLabel}>No data</div>
      </div>
    );
  }

  const keys = Object.keys(firstRow);
  const firstKey = keys[0] || "value";
  const value = firstRow[firstKey];
  const numValue = typeof value === "number" ? value : 0;

  const displayFormat =
    valueFormat ||
    (firstKey.toLowerCase().includes("revenue") || firstKey.toLowerCase().includes("total")
      ? "currency"
      : "number");

  const formattedValue = createFormatter(displayFormat)(numValue);

  return (
    <div className={styles.container}>
      <div className={styles.value}>{formattedValue}</div>
      <div className={styles.label}>{firstKey.replace(/_/g, " ")}</div>
    </div>
  );
}
