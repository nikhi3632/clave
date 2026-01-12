/**
 * TableView component styles
 */

import { tableStyles } from "../shared";

export const tableViewStyles = {
  ...tableStyles,
  // Override container with scrollable version
  container: "overflow-x-auto max-h-[400px] overflow-y-auto",
};
