"use client";

import { useState, useCallback } from "react";
import { WidgetData, ApiError, QueryResponse } from "@/types";
import { getApiUrl } from "@/lib/api";

interface UseQueryReturn {
  widgets: WidgetData[];
  isLoading: boolean;
  error: ApiError | null;
  lastQuery: string | null;
  handleQuery: (query: string) => Promise<void>;
  handleRetry: () => void;
  handleDismissError: () => void;
  handleRemoveWidget: (id: string) => void;
}

export function useQuery(): UseQueryReturn {
  const [widgets, setWidgets] = useState<WidgetData[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [lastQuery, setLastQuery] = useState<string | null>(null);

  const handleQuery = useCallback(async (query: string) => {
    setIsLoading(true);
    setError(null);
    setLastQuery(query);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000);

    try {
      const response = await fetch(getApiUrl("/api/query"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      const result = await response.json();

      if (!response.ok) {
        const errorResponse = result as { error?: string; code?: string; retryable?: boolean };
        throw {
          message: errorResponse.error || "Failed to process query",
          code: errorResponse.code,
          retryable: errorResponse.retryable ?? response.status >= 500,
        };
      }

      const successResult = result as QueryResponse;

      const newWidget: WidgetData = {
        id: crypto.randomUUID(),
        query: successResult.query,
        title: successResult.title,
        chartType: successResult.chartType,
        data: successResult.data,
        xAxis: successResult.xAxis,
        yAxis: successResult.yAxis,
        dataKey: successResult.dataKey,
        nameKey: successResult.nameKey,
        valueFormat: successResult.valueFormat,
        summary: successResult.summary,
        sql: successResult.sql,
        dataRange: successResult.dataRange,
        drillDown: successResult.drillDown,
      };

      setWidgets((prev) => [newWidget, ...prev]);
      setLastQuery(null);
    } catch (err) {
      clearTimeout(timeoutId); // Ensure timeout is cleared on error
      if (err instanceof Error) {
        if (err.name === "AbortError") {
          setError({
            message: "Request timed out. Please try again.",
            code: "TIMEOUT",
            retryable: true,
          });
        } else {
          setError({
            message: err.message,
            retryable: true,
          });
        }
      } else if (typeof err === "object" && err !== null && "message" in err) {
        setError(err as ApiError);
      } else {
        setError({
          message: "An unexpected error occurred",
          retryable: true,
        });
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleRetry = useCallback(() => {
    if (lastQuery) {
      handleQuery(lastQuery);
    }
  }, [lastQuery, handleQuery]);

  const handleDismissError = useCallback(() => {
    setError(null);
    setLastQuery(null);
  }, []);

  const handleRemoveWidget = useCallback((id: string) => {
    setWidgets((prev) => prev.filter((w) => w.id !== id));
  }, []);

  return {
    widgets,
    isLoading,
    error,
    lastQuery,
    handleQuery,
    handleRetry,
    handleDismissError,
    handleRemoveWidget,
  };
}
