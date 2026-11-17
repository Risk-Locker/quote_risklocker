import type { LedgerDensity, LedgerOptionalColumn } from "./types";

/**
 * Single source of truth for /ledger column visibility and widths.
 * Both the <thead> (LedgerTable) and every row (TenureRow) resolve columns here,
 * so header and body cells can never drift out of alignment.
 */

/** Optional columns automatically collapsed in Compact mode (secondary metadata). */
const COMPACT_AUTO_HIDDEN: readonly LedgerOptionalColumn[] = ["created_at", "pic"];

export interface LedgerColumnLayout {
  isCompact: boolean;
  showQuotes: boolean;
  showCreatedAt: boolean;
  showPic: boolean;
  /** Total rendered column count (used for empty/loading colSpan). */
  columnCount: number;
  /** Optional columns hidden only because Compact mode is active. */
  compactCollapsed: LedgerOptionalColumn[];
  cellPadding: string;
  widths: {
    select: string;
    vehicle: string;
    coverage: string;
    stage: string;
    quotes: string;
    createdAt: string;
    pic: string;
    actions: string;
  };
}

const COMPACT_WIDTHS: LedgerColumnLayout["widths"] = {
  select: "w-11 min-w-[44px] max-w-[44px]",
  vehicle: "min-w-[168px] max-w-[168px]",
  coverage: "min-w-[114px]",
  stage: "min-w-[210px]",
  quotes: "min-w-[160px] max-w-[160px]",
  createdAt: "min-w-[130px]",
  pic: "min-w-[140px]",
  actions: "min-w-[92px]",
};

const COMFORTABLE_WIDTHS: LedgerColumnLayout["widths"] = {
  select: "w-14 min-w-[56px] max-w-[56px]",
  vehicle: "min-w-[210px]",
  coverage: "min-w-[160px]",
  stage: "min-w-[320px]",
  quotes: "min-w-[220px]",
  createdAt: "min-w-[140px]",
  pic: "min-w-[150px]",
  actions: "min-w-[150px]",
};

/** Left offset of the sticky Vehicle column; must equal the select column width. */
export function stickyVehicleOffset(isCompact: boolean): string {
  return isCompact ? "left-[44px]" : "left-[56px]";
}

export function resolveLedgerColumns(
  density: LedgerDensity,
  hiddenColumns: readonly string[],
): LedgerColumnLayout {
  const isCompact = density === "compact";
  const isHidden = (col: LedgerOptionalColumn) =>
    hiddenColumns.includes(col) || (isCompact && COMPACT_AUTO_HIDDEN.includes(col));

  const showQuotes = !isHidden("last_activity");
  const showCreatedAt = !isHidden("created_at");
  const showPic = !isHidden("pic");

  const compactCollapsed = isCompact
    ? COMPACT_AUTO_HIDDEN.filter((col) => !hiddenColumns.includes(col))
    : [];

  return {
    isCompact,
    showQuotes,
    showCreatedAt,
    showPic,
    // select + vehicle + coverage + stage + actions = 5 fixed columns
    columnCount: 5 + Number(showQuotes) + Number(showCreatedAt) + Number(showPic),
    compactCollapsed,
    cellPadding: isCompact ? "py-1.5 px-2" : "py-3 px-3",
    widths: isCompact ? COMPACT_WIDTHS : COMFORTABLE_WIDTHS,
  };
}
