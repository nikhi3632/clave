"use client";

import { useEffect, useState } from "react";
import { CloseIcon } from "./ui/Icon";
import { getApiUrl } from "@/lib/api";
import { drillDownModalStyles as styles } from "@/styles/drillDownModal";

interface DrillDownFilters {
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
  order_sales_cents: number;
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
  sales_cents: number;
  tax_cents: number;
  tip_cents: number;
  total_cents: number;
}

interface DrillDownSummary {
  item_count: number;
  order_count: number;
  total_quantity: number;
  primary_value: number;
  primary_label: string;
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
        sales_cents: item.order_sales_cents || 0,
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
        if (filters.summarySQL) params.set("summarySQL", filters.summarySQL);
        if (filters.summaryLabel) params.set("summaryLabel", filters.summaryLabel);

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
          setError(data.detail?.error || data.error || "Failed to fetch data");
          return;
        }

        setOrders(data.orders || []);
        setSummary(data.summary || null);
      } catch {
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

  // Determine if we should show order-level totals
  // When filtering by product/category, hide order totals (they don't match item-level revenue)
  // When filtering by location/date/source/channel, show full order details
  const showOrderTotals = !filters.product && !filters.category;

  return (
    <div className={styles.overlay}>
      <div className={styles.backdrop} onClick={onClose} />

      <div className={styles.container}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerContent}>
            <h2 className={styles.title}>{title}</h2>
            <p className={styles.subtitle}>
              {isLoading ? "Loading..." : error ? "Error loading data" : `${orders.length} order items`}
            </p>
          </div>
          <button onClick={onClose} className={styles.closeBtn}>
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className={styles.content}>
          {isLoading && (
            <div className={styles.loadingContainer}>
              <div className={styles.loadingSpinner} />
            </div>
          )}

          {error && (
            <div className={styles.errorContainer}>
              <div className={styles.errorMessage}>{error}</div>
              <p className={styles.errorHint}>
                Try clicking on a different data point or check the console for details.
              </p>
            </div>
          )}

          {!isLoading && !error && orders.length === 0 && (
            <div className={styles.emptyContainer}>
              No orders found for this selection
            </div>
          )}

          {!isLoading && !error && orders.length > 0 && (
            <>
              {/* Mobile: Grouped card layout */}
              <div className={styles.mobileOnly}>
                {groupByOrder(orders).map((group) => (
                  <div key={group.order_id} className={styles.mobileCard}>
                    <div className={styles.mobileCardHeader}>
                      <div className={styles.mobileCardHeaderRow}>
                        <span className={styles.mobileCardTitle}>
                          {formatDateTime(group.created_at)}
                        </span>
                        <span className={styles.badgeSmall}>{group.source}</span>
                      </div>
                      <span className={styles.mobileCardSubtitle}>{group.location}</span>
                    </div>

                    <div className={styles.mobileCardContent}>
                      {group.items.map((item, i) => (
                        <div key={i} className={styles.mobileCardItem}>
                          <span className={styles.mobileCardItemName}>
                            {item.product} <span className={styles.mobileCardItemQty}>x{item.quantity}</span>
                          </span>
                          <span className={styles.mobileCardItemPrice}>
                            {formatCurrency(item.item_total_cents)}
                          </span>
                        </div>
                      ))}
                    </div>

                    {showOrderTotals && (
                      <div className={styles.mobileCardFooter}>
                        <div className={styles.mobileCardFooterRow}>
                          <span>Sales</span>
                          <span>{formatCurrency(group.sales_cents)}</span>
                        </div>
                        {group.tax_cents > 0 && (
                          <div className={styles.mobileCardFooterRow}>
                            <span>Tax</span>
                            <span>{formatCurrency(group.tax_cents)}</span>
                          </div>
                        )}
                        {group.tip_cents > 0 && (
                          <div className={styles.mobileCardFooterRow}>
                            <span>Tip</span>
                            <span>{formatCurrency(group.tip_cents)}</span>
                          </div>
                        )}
                        <div className={styles.mobileCardTotal}>
                          <span>Total</span>
                          <span>{formatCurrency(group.total_cents)}</span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Desktop: Grouped by order */}
              <div className={styles.desktopOnly}>
                {groupByOrder(orders).map((group) => (
                  <div key={group.order_id} className={styles.orderCard}>
                    <div className={styles.orderHeader}>
                      <div className={styles.orderHeaderLeft}>
                        <span className={styles.orderHeaderTime}>
                          {formatDateTime(group.created_at)}
                        </span>
                        <span className={styles.badge}>{group.source}</span>
                        <span className={styles.orderHeaderLocation}>{group.location}</span>
                      </div>
                      <span className={styles.orderHeaderId}>
                        {group.order_id.slice(0, 20)}...
                      </span>
                    </div>

                    <table className={styles.orderTable}>
                      <tbody className={styles.orderTableBody}>
                        {group.items.map((item, i) => (
                          <tr key={i} className={styles.orderTableRow}>
                            <td className={styles.orderTableCell}>{item.product}</td>
                            <td className={styles.orderTableCellMuted}>x{item.quantity}</td>
                            <td className={styles.orderTableCellPrice}>
                              @ {formatCurrency(item.unit_price_cents)}
                            </td>
                            <td className={styles.orderTableCellTotal}>
                              {formatCurrency(item.item_total_cents)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    {showOrderTotals && (
                      <div className={styles.orderFooter}>
                        <div className={styles.orderFooterRow}>
                          <span className={styles.orderFooterItem}>
                            Sales: {formatCurrency(group.sales_cents)}
                          </span>
                          {group.tax_cents > 0 && (
                            <span className={styles.orderFooterItem}>
                              Tax: {formatCurrency(group.tax_cents)}
                            </span>
                          )}
                          {group.tip_cents > 0 && (
                            <span className={styles.orderFooterItem}>
                              Tip: {formatCurrency(group.tip_cents)}
                            </span>
                          )}
                          <span className={styles.orderFooterTotal}>
                            Total: {formatCurrency(group.total_cents)}
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Footer with summary */}
        {!isLoading && orders.length > 0 && summary && (
          <div className={styles.footer}>
            <div className={styles.footerContent}>
              <span className={styles.footerCount}>
                {summary.total_quantity} {summary.total_quantity === 1 ? "unit" : "units"} from {summary.order_count} {summary.order_count === 1 ? "order" : "orders"}
              </span>
              <div className={styles.footerTotals}>
                <span className={styles.footerRevenue}>
                  {summary.primary_label}: {formatCurrency(summary.primary_value)}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
