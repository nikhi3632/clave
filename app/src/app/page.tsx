"use client";

import { Header } from "@/components/layout/Header";
import { QueryInput } from "@/components/QueryInput";
import { Widget } from "@/components/Widget";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { LoadingState } from "@/components/ui/LoadingState";
import { EmptyState } from "@/components/ui/EmptyState";
import { LineChartIcon } from "@/components/ui/Icon";
import { useQuery } from "@/hooks/useQuery";

export default function Dashboard() {
  const {
    widgets,
    isLoading,
    error,
    lastQuery,
    handleQuery,
    handleRetry,
    handleDismissError,
    handleRemoveWidget,
  } = useQuery();

  return (
    <ErrorBoundary>
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-zinc-950 dark:to-zinc-900">
        <Header />

        <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
          <div className="space-y-8">
            <QueryInput onSubmit={handleQuery} isLoading={isLoading} />

            {error && (
              <ErrorMessage
                error={error}
                onRetry={handleRetry}
                onDismiss={handleDismissError}
                isLoading={isLoading}
                canRetry={!!lastQuery}
              />
            )}

            {isLoading && <LoadingState />}

            {widgets.length === 0 && !isLoading && !error && (
              <EmptyState
                icon={<LineChartIcon className="w-8 h-8 text-slate-400 dark:text-zinc-500" />}
                title="No visualizations yet"
                description="Ask a question about your restaurant data to generate your first chart"
              />
            )}

            {widgets.length > 0 && (
              <div className="grid grid-cols-1 gap-6">
                {widgets.map((widget) => (
                  <ErrorBoundary key={widget.id}>
                    <Widget widget={widget} onRemove={handleRemoveWidget} />
                  </ErrorBoundary>
                ))}
              </div>
            )}
          </div>
        </main>
      </div>
    </ErrorBoundary>
  );
}
