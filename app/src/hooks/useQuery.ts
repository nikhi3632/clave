"use client";

import { useState, useCallback } from "react";
import { WidgetData, ApiError, QueryResponse } from "@/types";
import { getApiUrl } from "@/lib/api";

// User-friendly error messages for known error codes
const ERROR_MESSAGES: Record<string, string> = {
  TIMEOUT: "Request timed out. Please try again.",
  NETWORK_ERROR: "Unable to connect. Please check your internet connection.",
  RATE_LIMIT: "Too many requests. Please wait a moment and try again.",
  AUTH_ERROR: "Service configuration error. Please contact support.",
  PARSE_ERROR: "Couldn't process that query. Please try rephrasing.",
  INVALID_INPUT: "Please enter a valid question.",
  INVALID_SQL: "Couldn't generate a valid query. Please try rephrasing.",
  INVALID_RESPONSE: "Couldn't process the response. Please try again.",
  QUERY_ERROR: "Unable to fetch data. Please try again.",
  CONNECTION_ERROR: "Unable to connect to database. Please try again.",
  SYNTAX_ERROR: "Query error. Please try rephrasing your question.",
};

// Get user-friendly message, falling back to provided message or generic
function getFriendlyMessage(code?: string, fallback?: string): string {
  if (code && ERROR_MESSAGES[code]) {
    return ERROR_MESSAGES[code];
  }
  // If fallback looks like a technical error, use generic message
  if (fallback && (
    fallback.includes("Error:") ||
    fallback.includes("error:") ||
    fallback.includes("Exception") ||
    fallback.includes("failed:") ||
    fallback.includes("undefined") ||
    fallback.includes("null")
  )) {
    return "Something went wrong. Please try again.";
  }
  return fallback || "Something went wrong. Please try again.";
}

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
          message: getFriendlyMessage(errorResponse.code, errorResponse.error),
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
            message: getFriendlyMessage("TIMEOUT"),
            code: "TIMEOUT",
            retryable: true,
          });
        } else if (err.message === "Failed to fetch") {
          setError({
            message: getFriendlyMessage("NETWORK_ERROR"),
            code: "NETWORK_ERROR",
            retryable: true,
          });
        } else {
          setError({
            message: getFriendlyMessage(undefined, err.message),
            retryable: true,
          });
        }
      } else if (typeof err === "object" && err !== null && "message" in err) {
        setError(err as ApiError);
      } else {
        setError({
          message: "Something went wrong. Please try again.",
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
