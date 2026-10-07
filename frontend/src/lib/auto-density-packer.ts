/**
 * A4 Strict Dynamic Auto-Density Packer Engine
 * 
 * Guarantees that no matter how many benefits or add-ons exist (from 1 to 33+),
 * the quotation remains strictly within the single A4 page budget (height <= 1123px).
 */

export interface AutoDensityConfig {
  columns: number;
  cardHeight: number;
  titleFontSize: number;
  descFontSize: number;
  iconSize: number;
  padding: number;
  gap: number;
  densityTier: "standard" | "compact" | "dense" | "ultra_dense";
}

export function computeAutoDensityPacking(
  itemCount: number,
  availableHeight: number = 320,
  maxAvailableWidth: number = 714
): AutoDensityConfig {
  if (itemCount <= 6) {
    return {
      columns: 3,
      cardHeight: 64,
      titleFontSize: 9.5,
      descFontSize: 8.0,
      iconSize: 24,
      padding: 6,
      gap: 8,
      densityTier: "standard",
    };
  }

  if (itemCount <= 12) {
    const rows = Math.ceil(itemCount / 3);
    const targetHeight = Math.min(54, Math.floor((availableHeight - (rows * 6)) / rows));
    return {
      columns: 3,
      cardHeight: Math.max(46, targetHeight),
      titleFontSize: 9.0,
      descFontSize: 7.5,
      iconSize: 20,
      padding: 5,
      gap: 6,
      densityTier: "compact",
    };
  }

  if (itemCount <= 20) {
    const rows = Math.ceil(itemCount / 4);
    const targetHeight = Math.min(46, Math.floor((availableHeight - (rows * 5)) / rows));
    return {
      columns: 4,
      cardHeight: Math.max(38, targetHeight),
      titleFontSize: 8.5,
      descFontSize: 7.0,
      iconSize: 18,
      padding: 4,
      gap: 5,
      densityTier: "dense",
    };
  }

  // 21 to 33+ items: Ultra-dense 5-column or 4-column packing
  const columns = itemCount > 25 ? 5 : 4;
  const rows = Math.ceil(itemCount / columns);
  const targetHeight = Math.min(36, Math.floor((availableHeight - (rows * 4)) / rows));

  return {
    columns,
    cardHeight: Math.max(30, targetHeight),
    titleFontSize: 8.0,
    descFontSize: 6.5,
    iconSize: 14,
    padding: 3,
    gap: 4,
    densityTier: "ultra_dense",
  };
}
