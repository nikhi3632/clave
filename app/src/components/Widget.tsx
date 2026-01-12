"use client";

import { useState } from "react";
import { WidgetData, DrillDownFilters } from "@/types";
import { ChartWrapper } from "./charts";
import { DrillDownModal } from "./DrillDownModal";
import { Card, CardHeader, CardContent, CardFooter } from "./ui/Card";
import { CloseIcon, ChevronDownIcon, CalendarIcon, chartTypeIcons } from "./ui/Icon";
import { widgetStyles as styles } from "@/styles/widget";

const showSqlEnabled = process.env.NEXT_PUBLIC_SHOW_SQL === "true";

interface WidgetProps {
  widget: WidgetData;
  onRemove: (id: string) => void;
}

export function Widget({ widget, onRemove }: WidgetProps) {
  const [showSql, setShowSql] = useState(false);
  const [drillDownFilters, setDrillDownFilters] = useState<DrillDownFilters | null>(null);

  const ChartIcon = chartTypeIcons[widget.chartType];

  return (
    <Card className={styles.card}>
      <CardHeader className={styles.header}>
        <div className={styles.headerContent}>
          <div className={styles.iconWrapper}>
            <ChartIcon className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h3 className={styles.title}>{widget.title}</h3>
            <p className={styles.subtitle}>{widget.query}</p>
          </div>
        </div>
        <button
          onClick={() => onRemove(widget.id)}
          className={styles.removeBtn}
          aria-label="Remove widget"
        >
          <CloseIcon className="w-4 h-4" />
        </button>
      </CardHeader>

      <CardContent>
        <ChartWrapper
          type={widget.chartType}
          data={widget.data}
          xAxis={widget.xAxis}
          yAxis={widget.yAxis}
          dataKey={widget.dataKey}
          nameKey={widget.nameKey}
          valueFormat={widget.valueFormat}
          summary={widget.summary}
          onDataClick={setDrillDownFilters}
        />
      </CardContent>

      {widget.chartType !== "info" && (
        <CardFooter>
          <p className={styles.summary}>{widget.summary}</p>
        </CardFooter>
      )}

      <div className={styles.metaBar}>
        <div className={styles.metaContent}>
          <div className={styles.metaText}>
            <CalendarIcon className="w-3.5 h-3.5" />
            <span>Data: {widget.dataRange}</span>
          </div>
          {showSqlEnabled && (
            <button onClick={() => setShowSql(!showSql)} className={styles.sqlBtn}>
              <span className="font-medium">View SQL</span>
              <ChevronDownIcon
                className={`w-4 h-4 transition-transform ${showSql ? "rotate-180" : ""}`}
              />
            </button>
          )}
        </div>
        {showSqlEnabled && showSql && (
          <div className={styles.sqlContainer}>
            <pre className={styles.sqlPre}>{widget.sql}</pre>
          </div>
        )}
      </div>

      {drillDownFilters && (
        <DrillDownModal
          filters={drillDownFilters}
          onClose={() => setDrillDownFilters(null)}
        />
      )}
    </Card>
  );
}
