"use client";

import { useEffect, useState } from "react";
import { CloseIcon } from "./ui/Icon";
import { getApiUrl } from "@/lib/api";

interface DrillDownFilters {
  product?: string;
  location?: string;
  date?: string;
  source?: string;
  channel?: string;
  payment_type?: string;
  category?: string;
}

interface OrderItem {
  order_id: string;
  source: string;
  channel: string;
  payment_type: string | null;
  location: string;
  product: string;
  category: string;
  quantity: number;
  unit_price_cents: number;
  item_total_cents: number;
  order_total_cents: number;
  created_at: string;
}

interface DrillDownModalProps {
  filters: DrillDownFilters;
  onClose: () => void;
}

function formatCurrency(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function DrillDownModal({ filters, onClose }: DrillDownModalProps) {
  const [orders, setOrders] = useState<OrderItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      setIsLoading(true);
      setError(null);

      try {
        const params = new URLSearchParams();
        if (filters.product) params.set("product", filters.product);
        if (filters.location) params.set("location", filters.location);
        if (filters.date) params.set("date", filters.date);
        if (filters.source) params.set("source", filters.source);
        if (filters.channel) params.set("channel", filters.channel);
        if (filters.payment_type) params.set("payment_type", filters.payment_type);
        if (filters.category) params.set("category", filters.category);

        // Check if we have at least one valid filter
        const hasValidFilter = filters.product || filters.location || filters.date || filters.source || filters.channel || filters.payment_type || filters.category;
        if (!hasValidFilter) {
          setError("No valid filter selected");
          setIsLoading(false);
          return;
        }

        const response = await fetch(getApiUrl(`/api/drill-down?${params.toString()}`));
        const data = await response.json();

        if (!response.ok) {
          console.error("Drill-down error:", data);
          setError(data.error || "Failed to fetch data");
          return;
        }

        setOrders(data.orders || []);
      } catch (err) {
        console.error("Drill-down fetch error:", err);
        setError("Failed to fetch order details");
      } finally {
        setIsLoading(false);
      }
    }

    fetchData();
  }, [filters]);

  // Close on escape key
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  // Build title from filters
  const filterParts: string[] = [];
  if (filters.product) filterParts.push(filters.product);
  if (filters.category) filterParts.push(`Category: ${filters.category}`);
  if (filters.payment_type) filterParts.push(`Payment: ${filters.payment_type}`);
  if (filters.location) filterParts.push(`@ ${filters.location}`);
  if (filters.date) filterParts.push(`on ${filters.date}`);
  if (filters.source) filterParts.push(`(${filters.source})`);
  if (filters.channel) filterParts.push(`[${filters.channel}]`);
  const title = filterParts.length > 0 ? filterParts.join(" ") : "Order Details";

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-white dark:bg-zinc-900 rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] mx-2 sm:mx-4 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 py-4 border-b border-slate-200 dark:border-zinc-800">
          <div className="min-w-0 flex-1 mr-4">
            <h2 className="text-base sm:text-lg font-semibold text-slate-900 dark:text-zinc-100 truncate">
              {title}
            </h2>
            <p className="text-sm text-slate-500 dark:text-zinc-400">
              {isLoading ? "Loading..." : error ? "Error loading data" : `${orders.length} order items`}
            </p>
          </div>
          <button
            onClick={onClose}
            className="flex-shrink-0 p-2 text-slate-400 hover:text-slate-600 dark:hover:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 rounded-lg transition-colors"
          >
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4 sm:p-6">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" />
            </div>
          )}

          {error && (
            <div className="text-center py-12">
              <div className="text-red-500 mb-2">{error}</div>
              <p className="text-sm text-slate-500 dark:text-zinc-400">
                Try clicking on a different data point or check the console for details.
              </p>
            </div>
          )}

          {!isLoading && !error && orders.length === 0 && (
            <div className="text-center py-12 text-slate-500 dark:text-zinc-400">
              No orders found for this selection
            </div>
          )}

          {!isLoading && !error && orders.length > 0 && (
            <>
              {/* Mobile: Card layout */}
              <div className="sm:hidden space-y-3">
                {orders.map((order, i) => (
                  <div
                    key={`${order.order_id}-${i}`}
                    className="bg-slate-50 dark:bg-zinc-800 rounded-lg p-4"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-medium text-slate-900 dark:text-zinc-100">
                        {order.product}
                      </span>
                      <span className="font-medium text-slate-900 dark:text-zinc-100">
                        {formatCurrency(order.item_total_cents)}
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs text-slate-500 dark:text-zinc-400">
                      <span>{formatDateTime(order.created_at)}</span>
                      <span>•</span>
                      <span>{order.location}</span>
                      <span>•</span>
                      <span className="px-1.5 py-0.5 bg-slate-200 dark:bg-zinc-700 rounded">
                        {order.source}
                      </span>
                    </div>
                    <div className="flex justify-between mt-2 text-sm text-slate-600 dark:text-zinc-400">
                      <span>Qty: {order.quantity}</span>
                      <span>@ {formatCurrency(order.unit_price_cents)}</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Desktop: Table layout */}
              <div className="hidden sm:block overflow-x-auto">
                <table className="min-w-full">
                  <thead className="bg-slate-50 dark:bg-zinc-800 sticky top-0">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-zinc-400 uppercase">
                        Time
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-zinc-400 uppercase">
                        Product
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-zinc-400 uppercase">
                        Source
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-slate-600 dark:text-zinc-400 uppercase">
                        Location
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600 dark:text-zinc-400 uppercase">
                        Qty
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600 dark:text-zinc-400 uppercase">
                        Price
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-slate-600 dark:text-zinc-400 uppercase">
                        Total
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                    {orders.map((order, i) => (
                      <tr
                        key={`${order.order_id}-${i}`}
                        className="hover:bg-slate-50 dark:hover:bg-zinc-800/50"
                      >
                        <td className="px-4 py-3 text-sm text-slate-600 dark:text-zinc-400 whitespace-nowrap">
                          {formatDateTime(order.created_at)}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-900 dark:text-zinc-100 font-medium">
                          {order.product}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300">
                            {order.source}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600 dark:text-zinc-400">
                          {order.location}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600 dark:text-zinc-400 text-right">
                          {order.quantity}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-600 dark:text-zinc-400 text-right">
                          {formatCurrency(order.unit_price_cents)}
                        </td>
                        <td className="px-4 py-3 text-sm text-slate-900 dark:text-zinc-100 font-medium text-right">
                          {formatCurrency(order.item_total_cents)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        {!isLoading && orders.length > 0 && (
          <div className="px-4 sm:px-6 py-3 border-t border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/50">
            <div className="flex justify-between text-sm">
              <span className="text-slate-500 dark:text-zinc-400">
                {orders.length} {orders.length === 1 ? "item" : "items"}
              </span>
              <span className="font-medium text-slate-900 dark:text-zinc-100">
                Total:{" "}
                {formatCurrency(
                  orders.reduce((sum, o) => sum + o.item_total_cents, 0)
                )}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
