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
                {col.replace(/_/g, " ")}
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
                const cellFormat =
                  colLower.includes("revenue") ||
                  colLower.includes("price") ||
                  colLower.includes("total")
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
