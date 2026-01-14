"use client";

import { ValueFormat, DrillDownFilters, DrillDownConfig } from "@/types";
import { createFormatter } from "./chartTheme";
import { tableViewStyles as styles } from "@/styles/charts/table";

interface TableViewProps {
  data: Record<string, unknown>[];
  valueFormat?: ValueFormat;
  drillDown?: DrillDownConfig;
  onDataClick?: (filters: DrillDownFilters) => void;
}

export function TableView({ data, valueFormat, drillDown, onDataClick }: TableViewProps) {
  const columns = Object.keys(data[0] || {});

  // Check if drill-down is enabled
  const isDrillDownEnabled = drillDown?.enabled && onDataClick;

  const handleRowClick = (row: Record<string, unknown>) => {
    if (!isDrillDownEnabled || !drillDown?.type || !drillDown?.column) return;

    const value = row[drillDown.column];
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
    <div className={styles.container}>
      <table className={styles.table}>
        <thead className={styles.thead}>
          <tr>
            {columns.map((col) => (
              <th key={col} className={styles.th}>
                {col.replace(/_cents$/i, "").replace(/_/g, " ")}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className={styles.tbody}>
          {data.map((row, i) => (
            <tr
              key={i}
              className={isDrillDownEnabled ? styles.trClickable : styles.tr}
              onClick={() => handleRowClick(row)}
            >
              {columns.map((col) => {
                const cellValue = row[col];
                const isNumeric = typeof cellValue === "number";
                const colLower = col.toLowerCase();
                // Determine format based on column name
                // Count/quantity columns → plain number
                // Currency columns (_cents, revenue, price, tax, tip) → currency
                const isCountColumn =
                  colLower.includes("units") ||
                  colLower.includes("count") ||
                  colLower.includes("quantity") ||
                  colLower.includes("orders");
                const isCurrencyColumn =
                  colLower.endsWith("_cents") ||
                  colLower.includes("sales") ||
                  colLower.includes("price") ||
                  colLower.includes("tax") ||
                  colLower.includes("tip");
                const cellFormat = isCountColumn
                  ? "number"
                  : isCurrencyColumn
                    ? "currency"
                    : valueFormat;
                return (
                  <td key={col} className={styles.td}>
                    {isNumeric
                      ? createFormatter(cellFormat)(cellValue as number)
                      : String(cellValue ?? "")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
