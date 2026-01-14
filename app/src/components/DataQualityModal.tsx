"use client";

import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabase";
import { CloseIcon } from "./ui/Icon";
import { dataQualityModalStyles as styles } from "@/styles/dataQualityModal";

// Dynamic source breakdown - no hardcoded vendor names
interface SourceStats {
  orders: number;
  sales_cents: number;
  tax_cents: number;
  tip_cents: number;
  total_cents: number;
}

interface ReconciliationData {
  total_orders: number;
  total_sales_cents: number;
  total_tax_cents: number;
  total_tip_cents: number;
  total_collected_cents: number;
  total_products: number;
  total_categories: number;
  total_locations: number;
  min_date: string;
  max_date: string;
  // Dynamic source breakdown as JSONB
  source_breakdown: Record<string, SourceStats>;
  // Quality
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
    <div className={styles.overlay}>
      <div className={styles.backdrop} onClick={onClose} />

      <div className={styles.container}>
        {/* Header */}
        <div className={styles.header}>
          <h2 className={styles.title}>Data Quality</h2>
          <button onClick={onClose} className={styles.closeBtn}>
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className={styles.content}>
          {isLoading && (
            <div className={styles.loading.container}>
              <div className={styles.loading.spinner} />
            </div>
          )}

          {error && <div className={styles.error}>{error}</div>}

          {!isLoading && !error && data && (
            <div className="space-y-6">
              {/* Summary Stats */}
              <div className={styles.statsGrid}>
                <div className={styles.statCard.container}>
                  <div className={styles.statCard.value}>
                    {formatCurrency(data.total_sales_cents)}
                  </div>
                  <div className={styles.statCard.label}>Sales</div>
                </div>
                <div className={styles.statCard.container}>
                  <div className={styles.statCard.value}>
                    {formatCurrency(data.total_tax_cents)}
                  </div>
                  <div className={styles.statCard.label}>Tax</div>
                </div>
                <div className={styles.statCard.container}>
                  <div className={styles.statCard.value}>
                    {formatCurrency(data.total_tip_cents)}
                  </div>
                  <div className={styles.statCard.label}>Tips</div>
                </div>
                <div className={styles.statCard.container}>
                  <div className={styles.statCard.value}>
                    {formatCurrency(data.total_collected_cents)}
                  </div>
                  <div className={styles.statCard.label}>Total Collected</div>
                </div>
              </div>

              {/* Orders, Products & Categories */}
              <div className={styles.statsGrid}>
                <div className={styles.statCard.container}>
                  <div className={styles.statCard.value}>
                    {data.total_orders.toLocaleString()}
                  </div>
                  <div className={styles.statCard.label}>Orders</div>
                </div>
                <div className={styles.statCard.container}>
                  <div className={styles.statCard.value}>{data.total_products}</div>
                  <div className={styles.statCard.label}>Products</div>
                </div>
                <div className={styles.statCard.container}>
                  <div className={styles.statCard.value}>{data.total_categories}</div>
                  <div className={styles.statCard.label}>Categories</div>
                </div>
              </div>

              {/* Source Breakdown - Dynamic from JSONB */}
              <div>
                <h3 className={styles.sectionTitle}>Breakdown by Source</h3>
                <div className={styles.sourceList}>
                  {Object.entries(data.source_breakdown)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([sourceName, stats]) => (
                      <div key={sourceName} className={styles.sourceRow}>
                        <span className={styles.sourceName}>
                          {sourceName.charAt(0).toUpperCase() + sourceName.slice(1)}
                        </span>
                        <span className={styles.sourceStats}>
                          {stats.orders} orders · {formatCurrency(stats.sales_cents)} sales
                          {stats.tax_cents > 0 && ` + ${formatCurrency(stats.tax_cents)} tax`}
                          {stats.tip_cents > 0 && ` + ${formatCurrency(stats.tip_cents)} tips`}
                          {" = "}
                          {formatCurrency(stats.total_cents)}
                        </span>
                      </div>
                    ))}
                </div>
              </div>

              {/* Data Quality Indicators */}
              <div>
                <h3 className={styles.sectionTitle}>Data Quality</h3>
                <div className={styles.qualityGrid}>
                  <div className={styles.qualityCard(data.error_count > 0, "error")}>
                    <div className={styles.qualityValue(data.error_count > 0, "error")}>
                      {data.error_count}
                    </div>
                    <div className={styles.qualityLabel}>Errors</div>
                  </div>
                  <div className={styles.qualityCard(data.warning_count > 0, "warning")}>
                    <div className={styles.qualityValue(data.warning_count > 0, "warning")}>
                      {data.warning_count}
                    </div>
                    <div className={styles.qualityLabel}>Warnings</div>
                  </div>
                  <div className={styles.qualityCard(data.products_without_category > 0, "warning")}>
                    <div className={styles.qualityValue(data.products_without_category > 0, "warning")}>
                      {data.products_without_category}
                    </div>
                    <div className={styles.qualityLabel}>Uncategorized</div>
                  </div>
                </div>
              </div>

              {/* Date Range */}
              <div className={styles.dateRange}>
                Data from {formatDate(data.min_date)} to {formatDate(data.max_date)} · {data.total_locations} locations
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
