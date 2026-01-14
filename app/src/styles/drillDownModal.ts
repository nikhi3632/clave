/**
 * DrillDownModal component styles
 */

import { modalStyles, tableStyles, spinnerStyles, badgeStyles, textStyles } from "./shared";

export const drillDownModalStyles = {
  // Base modal
  overlay: modalStyles.overlay,
  backdrop: modalStyles.backdrop,
  container: [
    modalStyles.container,
    "w-full max-w-4xl max-h-[90vh] mx-2 sm:mx-4 flex flex-col",
  ].join(" "),

  // Header
  header: [
    "flex items-center justify-between px-4 sm:px-6 py-4",
    "border-b border-slate-200 dark:border-zinc-800",
  ].join(" "),
  headerContent: "min-w-0 flex-1 mr-4",
  title: "text-base sm:text-lg font-semibold text-slate-900 dark:text-zinc-100 truncate",
  subtitle: textStyles.body,
  closeBtn: modalStyles.closeBtn,

  // Content area
  content: "flex-1 overflow-auto p-4 sm:p-6",

  // Loading state
  loadingContainer: spinnerStyles.container,
  loadingSpinner: spinnerStyles.spinner,

  // Error state
  errorContainer: "text-center py-12",
  errorMessage: "text-red-500 mb-2",
  errorHint: textStyles.body,

  // Empty state
  emptyContainer: "text-center py-12 text-slate-500 dark:text-zinc-400",

  // Mobile: Grouped card layout
  mobileOnly: "sm:hidden space-y-4",
  mobileCard: "bg-slate-50 dark:bg-zinc-800 rounded-lg overflow-hidden",
  mobileCardHeader: "px-4 py-2 border-b border-slate-200 dark:border-zinc-700",
  mobileCardHeaderRow: "flex justify-between items-center",
  mobileCardTitle: "text-sm font-medium text-slate-900 dark:text-zinc-100",
  mobileCardSubtitle: "text-xs text-slate-500 dark:text-zinc-400",
  mobileCardContent: "px-4 py-2 space-y-2",
  mobileCardItem: "flex justify-between text-sm",
  mobileCardItemName: "text-slate-900 dark:text-zinc-100",
  mobileCardItemQty: "text-slate-500",
  mobileCardItemPrice: "text-slate-900 dark:text-zinc-100 font-medium",
  mobileCardFooter: [
    "px-4 py-2 border-t border-slate-200 dark:border-zinc-700",
    "bg-slate-100 dark:bg-zinc-700/50",
  ].join(" "),
  mobileCardFooterRow: "flex justify-between text-xs text-slate-500 dark:text-zinc-400",
  mobileCardTotal: "flex justify-between text-sm font-semibold text-slate-900 dark:text-zinc-100 mt-1",

  // Desktop: Grouped by order
  desktopOnly: "hidden sm:block space-y-4",
  orderCard: "border border-slate-200 dark:border-zinc-700 rounded-lg overflow-hidden",
  orderHeader: "bg-slate-50 dark:bg-zinc-800 px-4 py-2 flex justify-between items-center",
  orderHeaderLeft: "flex items-center gap-3",
  orderHeaderTime: "text-sm font-medium text-slate-900 dark:text-zinc-100",
  orderHeaderId: "text-xs text-slate-400 dark:text-zinc-500 font-mono",
  orderHeaderLocation: "text-xs text-slate-500 dark:text-zinc-400",

  // Table inside order card
  orderTable: "min-w-full",
  orderTableBody: tableStyles.tbody,
  orderTableRow: tableStyles.tr,
  orderTableCell: "px-4 py-2 text-sm text-slate-900 dark:text-zinc-100",
  orderTableCellMuted: "px-4 py-2 text-sm text-slate-500 dark:text-zinc-400 text-right w-16",
  orderTableCellPrice: "px-4 py-2 text-sm text-slate-500 dark:text-zinc-400 text-right w-24",
  orderTableCellTotal: "px-4 py-2 text-sm text-slate-900 dark:text-zinc-100 font-medium text-right w-24",

  // Order totals
  orderFooter: [
    "bg-slate-50 dark:bg-zinc-800/50 px-4 py-2",
    "border-t border-slate-200 dark:border-zinc-700",
  ].join(" "),
  orderFooterRow: "flex justify-end gap-6 text-sm",
  orderFooterItem: "text-slate-500 dark:text-zinc-400",
  orderFooterTotal: "font-semibold text-slate-900 dark:text-zinc-100",

  // Badge
  badge: badgeStyles.default,
  badgeSmall: "px-2 py-0.5 bg-slate-200 dark:bg-zinc-700 rounded text-xs",

  // Summary footer
  footer: [
    "px-4 sm:px-6 py-3",
    "border-t border-slate-200 dark:border-zinc-800",
    "bg-slate-50 dark:bg-zinc-800/50",
  ].join(" "),
  footerContent: "flex flex-col sm:flex-row sm:justify-between gap-2 text-sm",
  footerCount: "text-slate-500 dark:text-zinc-400",
  footerTotals: "flex flex-wrap gap-x-4 gap-y-1 text-right",
  footerTotalItem: "text-slate-600 dark:text-zinc-400",
  footerRevenue: "font-semibold text-slate-900 dark:text-zinc-100",
};
