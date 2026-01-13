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
  order_subtotal_cents: number;
  order_tax_cents: number;
  order_tip_cents: number;
  order_total_cents: number;
  created_at: string;
}

interface GroupedOrder {
  order_id: string;
  source: string;
  channel: string;
  location: string;
  created_at: string;
  items: OrderItem[];
  subtotal_cents: number;
  tax_cents: number;
  tip_cents: number;
  total_cents: number;
}

interface DrillDownSummary {
  item_count: number;
  order_count: number;
  item_subtotal_cents: number;
  tax_cents: number;
  tip_cents: number;
  revenue_cents: number;
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

function groupByOrder(items: OrderItem[]): GroupedOrder[] {
  const groups = new Map<string, GroupedOrder>();

  for (const item of items) {
    if (!groups.has(item.order_id)) {
      groups.set(item.order_id, {
        order_id: item.order_id,
        source: item.source,
        channel: item.channel,
        location: item.location,
        created_at: item.created_at,
        items: [],
        subtotal_cents: item.order_subtotal_cents || 0,
        tax_cents: item.order_tax_cents || 0,
        tip_cents: item.order_tip_cents || 0,
        total_cents: item.order_total_cents || 0,
      });
    }
    groups.get(item.order_id)!.items.push(item);
  }

  // Sort by created_at descending
  return Array.from(groups.values()).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );
}

export function DrillDownModal({ filters, onClose }: DrillDownModalProps) {
  const [orders, setOrders] = useState<OrderItem[]>([]);
  const [summary, setSummary] = useState<DrillDownSummary | null>(null);
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
        setSummary(data.summary || null);
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
              {/* Mobile: Grouped card layout */}
              <div className="sm:hidden space-y-4">
                {groupByOrder(orders).map((group) => (
                  <div
                    key={group.order_id}
                    className="bg-slate-50 dark:bg-zinc-800 rounded-lg overflow-hidden"
                  >
                    {/* Order header */}
                    <div className="px-4 py-2 border-b border-slate-200 dark:border-zinc-700">
                      <div className="flex justify-between items-center">
                        <span className="text-sm font-medium text-slate-900 dark:text-zinc-100">
                          {formatDateTime(group.created_at)}
                        </span>
                        <span className="px-2 py-0.5 bg-slate-200 dark:bg-zinc-700 rounded text-xs">
                          {group.source}
                        </span>
                      </div>
                      <span className="text-xs text-slate-500 dark:text-zinc-400">
                        {group.location}
                      </span>
                    </div>

                    {/* Items */}
                    <div className="px-4 py-2 space-y-2">
                      {group.items.map((item, i) => (
                        <div key={i} className="flex justify-between text-sm">
                          <span className="text-slate-900 dark:text-zinc-100">
                            {item.product} <span className="text-slate-500">x{item.quantity}</span>
                          </span>
                          <span className="text-slate-900 dark:text-zinc-100 font-medium">
                            {formatCurrency(item.item_total_cents)}
                          </span>
                        </div>
                      ))}
                    </div>

                    {/* Order totals */}
                    <div className="px-4 py-2 border-t border-slate-200 dark:border-zinc-700 bg-slate-100 dark:bg-zinc-700/50">
                      <div className="flex justify-between text-xs text-slate-500 dark:text-zinc-400">
                        <span>Subtotal</span>
                        <span>{formatCurrency(group.subtotal_cents)}</span>
                      </div>
                      {group.tax_cents > 0 && (
                        <div className="flex justify-between text-xs text-slate-500 dark:text-zinc-400">
                          <span>Tax</span>
                          <span>{formatCurrency(group.tax_cents)}</span>
                        </div>
                      )}
                      {group.tip_cents > 0 && (
                        <div className="flex justify-between text-xs text-slate-500 dark:text-zinc-400">
                          <span>Tip</span>
                          <span>{formatCurrency(group.tip_cents)}</span>
                        </div>
                      )}
                      <div className="flex justify-between text-sm font-semibold text-slate-900 dark:text-zinc-100 mt-1">
                        <span>Total</span>
                        <span>{formatCurrency(group.total_cents)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Desktop: Grouped by order */}
              <div className="hidden sm:block space-y-4">
                {groupByOrder(orders).map((group) => (
                  <div
                    key={group.order_id}
                    className="border border-slate-200 dark:border-zinc-700 rounded-lg overflow-hidden"
                  >
                    {/* Order header */}
                    <div className="bg-slate-50 dark:bg-zinc-800 px-4 py-2 flex justify-between items-center">
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-medium text-slate-900 dark:text-zinc-100">
                          {formatDateTime(group.created_at)}
                        </span>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-slate-200 dark:bg-zinc-700 text-slate-700 dark:text-zinc-300">
                          {group.source}
                        </span>
                        <span className="text-xs text-slate-500 dark:text-zinc-400">
                          {group.location}
                        </span>
                      </div>
                      <span className="text-xs text-slate-400 dark:text-zinc-500 font-mono">
                        {group.order_id.slice(0, 20)}...
                      </span>
                    </div>

                    {/* Items */}
                    <table className="min-w-full">
                      <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
                        {group.items.map((item, i) => (
                          <tr key={i} className="hover:bg-slate-50 dark:hover:bg-zinc-800/30">
                            <td className="px-4 py-2 text-sm text-slate-900 dark:text-zinc-100">
                              {item.product}
                            </td>
                            <td className="px-4 py-2 text-sm text-slate-500 dark:text-zinc-400 text-right w-16">
                              x{item.quantity}
                            </td>
                            <td className="px-4 py-2 text-sm text-slate-500 dark:text-zinc-400 text-right w-24">
                              @ {formatCurrency(item.unit_price_cents)}
                            </td>
                            <td className="px-4 py-2 text-sm text-slate-900 dark:text-zinc-100 font-medium text-right w-24">
                              {formatCurrency(item.item_total_cents)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    {/* Order totals */}
                    <div className="bg-slate-50 dark:bg-zinc-800/50 px-4 py-2 border-t border-slate-200 dark:border-zinc-700">
                      <div className="flex justify-end gap-6 text-sm">
                        <span className="text-slate-500 dark:text-zinc-400">
                          Subtotal: {formatCurrency(group.subtotal_cents)}
                        </span>
                        {group.tax_cents > 0 && (
                          <span className="text-slate-500 dark:text-zinc-400">
                            Tax: {formatCurrency(group.tax_cents)}
                          </span>
                        )}
                        {group.tip_cents > 0 && (
                          <span className="text-slate-500 dark:text-zinc-400">
                            Tip: {formatCurrency(group.tip_cents)}
                          </span>
                        )}
                        <span className="font-semibold text-slate-900 dark:text-zinc-100">
                          Total: {formatCurrency(group.total_cents)}
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Footer with breakdown */}
        {!isLoading && orders.length > 0 && summary && (
          <div className="px-4 sm:px-6 py-3 border-t border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-800/50">
            <div className="flex flex-col sm:flex-row sm:justify-between gap-2 text-sm">
              <span className="text-slate-500 dark:text-zinc-400">
                {summary.item_count} {summary.item_count === 1 ? "item" : "items"} from {summary.order_count} {summary.order_count === 1 ? "order" : "orders"}
              </span>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-right">
                <span className="text-slate-600 dark:text-zinc-400">
                  Subtotal: {formatCurrency(summary.item_subtotal_cents)}
                </span>
                {summary.tax_cents > 0 && (
                  <span className="text-slate-600 dark:text-zinc-400">
                    Tax: {formatCurrency(summary.tax_cents)}
                  </span>
                )}
                {summary.tip_cents > 0 && (
                  <span className="text-slate-600 dark:text-zinc-400">
                    Tips: {formatCurrency(summary.tip_cents)}
                  </span>
                )}
                <span className="font-semibold text-slate-900 dark:text-zinc-100">
                  Revenue: {formatCurrency(summary.revenue_cents)}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
