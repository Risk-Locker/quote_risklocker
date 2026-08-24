export type GridPacking = {
  strategy?: "balanced" | "square_biased" | "staggered";
  alignment?: "start" | "center" | "end";
  aspectRatio?: number;
  referenceWidth?: number;
  referenceHeight?: number;
  gapRatio?: number;
  paddingRatio?: number;
  staggerRatio?: number;
};

export type PackedCard = { index: number; row: number; column: number; x: number; y: number; width: number; height: number; scale: number };
export type PackedGrid = { rows: number; columns: number; scale: number; cards: PackedCard[] };

function offset(extra: number, alignment: "start" | "center" | "end") {
  if (alignment === "start") return 0;
  if (alignment === "end") return extra;
  return extra / 2;
}

/** Exact TypeScript port of backend pack_fixed_grid(). */
export function packFixedGrid(count: number, width: number, height: number, input: GridPacking = {}): PackedGrid {
  if (!Number.isInteger(count) || count < 0 || width <= 0 || height <= 0 || count === 0) return { rows: 0, columns: 0, scale: 0, cards: [] };
  const strategy = input.strategy || "balanced";
  const alignment = input.alignment || "center";
  const aspect = Math.max(0.1, input.aspectRatio || 1.45);
  const referenceWidth = Math.max(1, input.referenceWidth || 180);
  const referenceHeight = Math.max(1, input.referenceHeight || 124);
  const gapRatio = Math.max(0, Math.min(1, input.gapRatio ?? 0.06));
  const paddingRatio = Math.max(0, Math.min(0.49, input.paddingRatio ?? 0.02));
  const staggerRatio = Math.max(0, Math.min(1, input.staggerRatio ?? 0.5));
  const padX = width * paddingRatio;
  const padY = height * paddingRatio;
  const usableWidth = Math.max(0.000001, width - padX * 2);
  const usableHeight = Math.max(0.000001, height - padY * 2);
  let best = { score: Number.NEGATIVE_INFINITY, scale: 0, rows: 1, columns: 1 };
  for (let columns = 1; columns <= count; columns += 1) {
    const rows = Math.ceil(count / columns);
    const gapX = usableWidth * gapRatio / columns;
    const gapY = usableHeight * gapRatio / rows;
    const staggerExtra = strategy === "staggered" && rows > 1 && columns > 1 ? 0.5 : 0;
    const cellWidth = (usableWidth - gapX * Math.max(columns - 1, 0)) / (columns + staggerExtra);
    const cellHeight = (usableHeight - gapY * Math.max(rows - 1, 0)) / rows;
    let cardWidth = Math.min(cellWidth, cellHeight * aspect);
    let cardHeight = cardWidth / aspect;
    if (cardHeight > cellHeight) { cardHeight = cellHeight; cardWidth = cardHeight * aspect; }
    const rawScale = Math.min(cardWidth / referenceWidth, cardHeight / referenceHeight);
    const scale = Math.min(1.0, rawScale);
    const densityShape = Math.abs(columns / rows - width / height);
    const squareBias = Math.abs(columns - rows) / Math.max(columns, rows);
    const penalty = strategy === "square_biased" ? squareBias : densityShape * 0.02;
    const score = scale - penalty * 0.000001;
    if (score > best.score || (score === best.score && columns < best.columns)) best = { score, scale, rows, columns };
  }
  const { rows, columns, scale } = best;
  const gapX = usableWidth * gapRatio / columns;
  const gapY = usableHeight * gapRatio / rows;
  const staggerExtra = strategy === "staggered" && rows > 1 && columns > 1 ? 0.5 : 0;
  const cellWidth = (usableWidth - gapX * Math.max(columns - 1, 0)) / (columns + staggerExtra);
  const cellHeight = (usableHeight - gapY * Math.max(rows - 1, 0)) / rows;
  const cardWidth = referenceWidth * scale;
  const cardHeight = referenceHeight * scale;
  const gridWidth = columns * cellWidth + Math.max(columns - 1, 0) * gapX + staggerExtra * cellWidth;
  const gridHeight = rows * cellHeight + Math.max(rows - 1, 0) * gapY;
  const originX = padX + offset(Math.max(0, usableWidth - gridWidth), alignment);
  const originY = padY + offset(Math.max(0, usableHeight - gridHeight), alignment);
  const cards: PackedCard[] = [];
  for (let index = 0; index < count; index += 1) {
    const row = Math.floor(index / columns);
    const column = index % columns;
    const rowCount = Math.min(columns, count - row * columns);
    const rowWidth = rowCount * cellWidth + Math.max(rowCount - 1, 0) * gapX;
    const wantedStagger = strategy === "staggered" && row % 2 ? cellWidth * staggerRatio : 0;
    const stagger = Math.min(wantedStagger, Math.max(0, usableWidth - rowWidth));
    const rowX = originX + offset(Math.max(0, gridWidth - rowWidth - staggerExtra * cellWidth), alignment) + stagger;
    const cellX = rowX + column * (cellWidth + gapX);
    const cellY = originY + row * (cellHeight + gapY);
    const x = Math.min(Math.max(cellX + (cellWidth - cardWidth) / 2, 0), width - cardWidth);
    const y = Math.min(Math.max(cellY + (cellHeight - cardHeight) / 2, 0), height - cardHeight);
    cards.push({ index, row, column, x, y, width: cardWidth, height: cardHeight, scale });
  }
  return { rows, columns, scale, cards };
}
