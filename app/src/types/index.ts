// Chart types
export type ChartType = "bar" | "line" | "pie" | "table" | "metric" | "info";
export type ValueFormat = "currency" | "number" | "percent";

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
}

// Drill-down filter for clicking on chart data
export interface DrillDownFilters {
  product?: string;
  location?: string;
  date?: string;
  source?: string;
  channel?: string;
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
  onDataClick?: (filters: DrillDownFilters) => void;
}
