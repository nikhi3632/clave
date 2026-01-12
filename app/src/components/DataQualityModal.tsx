"use client";

import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import { CloseIcon } from "./ui/Icon";

interface ReconciliationData {
  total_orders: number;
  total_revenue_cents: number;
  total_products: number;
  total_locations: number;
  min_date: string;
  max_date: string;
  toast_orders: number;
  toast_revenue_cents: number;
  doordash_orders: number;
  doordash_revenue_cents: number;
  square_orders: number;
  square_revenue_cents: number;
  products_without_category: number;
  error_count: number;
  warning_count: number;
}

interface DataQualityModalProps {
  onClose: () => void;
}

function formatCurrency(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function DataQualityModal({ onClose }: DataQualityModalProps) {
  const [data, setData] = useState<ReconciliationData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const { data: result, error: fetchError } = await supabase.client
          .from("reconciliation_totals")
          .select("*")
          .single();

        if (fetchError) {
          setError("Could not load data quality info");
          return;
        }

        setData(result as ReconciliationData);
      } catch {
        setError("Failed to fetch data");
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, []);

  // Close on escape key
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white dark:bg-zinc-900 rounded-xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-zinc-800">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-zinc-100">
            Data Quality
          </h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 dark:hover:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            </div>
          )}

          {error && (
            <div className="text-center py-8 text-red-500">{error}</div>
          )}

          {!isLoading && !error && data && (
            <div className="space-y-6">
              {/* Summary Stats */}
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-4 bg-slate-50 dark:bg-zinc-800 rounded-lg">
                  <div className="text-2xl font-bold text-slate-900 dark:text-zinc-100">
                    {formatCurrency(data.total_revenue_cents)}
                  </div>
                  <div className="text-sm text-slate-500 dark:text-zinc-400">
                    Total Revenue
                  </div>
                </div>
                <div className="text-center p-4 bg-slate-50 dark:bg-zinc-800 rounded-lg">
                  <div className="text-2xl font-bold text-slate-900 dark:text-zinc-100">
                    {data.total_orders.toLocaleString()}
                  </div>
                  <div className="text-sm text-slate-500 dark:text-zinc-400">
                    Orders
                  </div>
                </div>
                <div className="text-center p-4 bg-slate-50 dark:bg-zinc-800 rounded-lg">
                  <div className="text-2xl font-bold text-slate-900 dark:text-zinc-100">
                    {data.total_products}
                  </div>
                  <div className="text-sm text-slate-500 dark:text-zinc-400">
                    Products
                  </div>
                </div>
              </div>

              {/* Source Breakdown */}
              <div>
                <h3 className="text-sm font-medium text-slate-900 dark:text-zinc-100 mb-3">
                  Revenue by Source
                </h3>
                <div className="space-y-2">
                  {[
                    { name: "Toast", orders: data.toast_orders, revenue: data.toast_revenue_cents },
                    { name: "DoorDash", orders: data.doordash_orders, revenue: data.doordash_revenue_cents },
                    { name: "Square", orders: data.square_orders, revenue: data.square_revenue_cents },
                  ].map((source) => (
                    <div
                      key={source.name}
                      className="flex items-center justify-between py-2 px-3 bg-slate-50 dark:bg-zinc-800 rounded-lg"
                    >
                      <span className="font-medium text-slate-700 dark:text-zinc-300">
                        {source.name}
                      </span>
                      <span className="text-slate-600 dark:text-zinc-400">
                        {source.orders} orders · {formatCurrency(source.revenue)}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Data Quality Indicators */}
              <div>
                <h3 className="text-sm font-medium text-slate-900 dark:text-zinc-100 mb-3">
                  Data Quality
                </h3>
                <div className="grid grid-cols-3 gap-3">
                  <div className={`p-3 rounded-lg ${data.error_count > 0 ? "bg-red-50 dark:bg-red-900/20" : "bg-green-50 dark:bg-green-900/20"}`}>
                    <div className={`text-lg font-bold ${data.error_count > 0 ? "text-red-600 dark:text-red-400" : "text-green-600 dark:text-green-400"}`}>
                      {data.error_count}
                    </div>
                    <div className="text-xs text-slate-600 dark:text-zinc-400">Errors</div>
                  </div>
                  <div className={`p-3 rounded-lg ${data.warning_count > 0 ? "bg-amber-50 dark:bg-amber-900/20" : "bg-green-50 dark:bg-green-900/20"}`}>
                    <div className={`text-lg font-bold ${data.warning_count > 0 ? "text-amber-600 dark:text-amber-400" : "text-green-600 dark:text-green-400"}`}>
                      {data.warning_count}
                    </div>
                    <div className="text-xs text-slate-600 dark:text-zinc-400">Warnings</div>
                  </div>
                  <div className={`p-3 rounded-lg ${data.products_without_category > 0 ? "bg-amber-50 dark:bg-amber-900/20" : "bg-green-50 dark:bg-green-900/20"}`}>
                    <div className={`text-lg font-bold ${data.products_without_category > 0 ? "text-amber-600 dark:text-amber-400" : "text-green-600 dark:text-green-400"}`}>
                      {data.products_without_category}
                    </div>
                    <div className="text-xs text-slate-600 dark:text-zinc-400">Uncategorized</div>
                  </div>
                </div>
              </div>

              {/* Date Range */}
              <div className="text-center text-sm text-slate-500 dark:text-zinc-400 pt-2 border-t border-slate-200 dark:border-zinc-800">
                Data from {formatDate(data.min_date)} to {formatDate(data.max_date)} · {data.total_locations} locations
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
