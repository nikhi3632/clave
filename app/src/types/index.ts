// Chart types
export type ChartType = "bar" | "line" | "pie" | "table" | "metric" | "info";
export type ValueFormat = "currency" | "number" | "percent";
export type DrillDownType = "location" | "date" | "product" | "category" | "source" | "channel" | "payment_type";

// Drill-down configuration from LLM
export interface DrillDownConfig {
  enabled: boolean;
  type?: DrillDownType;
  column?: string;
  summarySQL?: string; // SQL to calculate drill-down summary (same logic as chart)
  summaryLabel?: string; // Display label for summary value
}

// Widget data structure
export interface WidgetData {
  id: string;
  query: string;
  title: string;
  chartType: ChartType;
  data: Record<string, unknown>[];
  xAxis?: string;
  yAxis?: string;
  dataKey?: string;
  nameKey?: string;
  valueFormat?: ValueFormat;
  summary: string;
  sql: string;
  dataRange: string;
  drillDown?: DrillDownConfig;
}

// API error structure
export interface ApiError {
  message: string;
  code?: string;
  retryable?: boolean;
}

// API response from /api/query
export interface QueryResponse {
  success: boolean;
  query: string;
  sql: string;
  chartType: ChartType;
  title: string;
  xAxis?: string;
  yAxis?: string;
  dataKey?: string;
  nameKey?: string;
  valueFormat?: ValueFormat;
  summary: string;
  data: Record<string, unknown>[];
  dataRange: string;
  drillDown?: DrillDownConfig;
}

// Drill-down filter for clicking on chart data
export interface DrillDownFilters {
  product?: string;
  location?: string;
  date?: string;
  source?: string;
  channel?: string;
  payment_type?: string;
  category?: string;
  summarySQL?: string;
  summaryLabel?: string;
}

// Chart component props
export interface ChartProps {
  type: ChartType;
  data: Record<string, unknown>[];
  xAxis?: string;
  yAxis?: string;
  dataKey?: string;
  nameKey?: string;
  valueFormat?: ValueFormat;
  summary?: string;
  drillDown?: DrillDownConfig;
  onDataClick?: (filters: DrillDownFilters) => void;
}

