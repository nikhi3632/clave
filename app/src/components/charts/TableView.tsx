"use client";

import { ValueFormat, DrillDownFilters } from "@/types";
import { createFormatter } from "./chartTheme";
import { tableViewStyles as styles } from "@/styles/charts/table";

interface TableViewProps {
  data: Record<string, unknown>[];
  valueFormat?: ValueFormat;
  onDataClick?: (filters: DrillDownFilters) => void;
}

export function TableView({ data, valueFormat, onDataClick }: TableViewProps) {
  const columns = Object.keys(data[0] || {});

  const handleRowClick = (row: Record<string, unknown>) => {
    if (!onDataClick) return;
    const filters: DrillDownFilters = {};

    for (const [key, value] of Object.entries(row)) {
      if (value === null || value === undefined || value === "") continue;

      const keyLower = key.toLowerCase();
      const strValue = String(value);

      if (keyLower.includes("product") || keyLower === "name" || keyLower === "canonical_name") {
        filters.product = strValue;
      } else if (keyLower.includes("location")) {
        filters.location = strValue;
      } else if (keyLower.includes("date")) {
        filters.date = strValue;
      } else if (keyLower === "source") {
        filters.source = strValue;
      } else if (keyLower === "channel") {
        filters.channel = strValue;
      }
    }

    if (Object.keys(filters).length > 0 && Object.values(filters).some(v => v)) {
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
              className={onDataClick ? styles.trClickable : styles.tr}
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
