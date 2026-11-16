/**
 * Utility helper to format vehicle display names with fallback to chassis numbers.
 */

export function getVehicleDisplayName(
  vehicleNo?: string | null,
  chassisNo?: string | null,
  engineNo?: string | null
): string {
  if (
    vehicleNo &&
    vehicleNo.trim() &&
    vehicleNo !== "UNPLATED" &&
    !vehicleNo.startsWith("CHASSIS:") &&
    !vehicleNo.startsWith("ENGINE:")
  ) {
    return vehicleNo.trim();
  }
  if (chassisNo && chassisNo.trim()) {
    return `Chassis: ${chassisNo.trim()}`;
  }
  if (vehicleNo && vehicleNo.startsWith("CHASSIS:")) {
    return `Chassis: ${vehicleNo.replace("CHASSIS:", "").trim()}`;
  }
  if (engineNo && engineNo.trim()) {
    return `Engine: ${engineNo.trim()}`;
  }
  if (vehicleNo && vehicleNo.startsWith("ENGINE:")) {
    return `Engine: ${vehicleNo.replace("ENGINE:", "").trim()}`;
  }
  return "No Plate (Blank)";
}

/**
 * Deduplicate brand and model when formatting full vehicle name.
 * e.g., brand: "HONDA", model: "HONDA CRF250" -> "HONDA CRF250"
 * e.g., brand: "HONDA", model: "CRF250" -> "HONDA CRF250"
 */
export function formatBrandAndModel(
  brand?: string | null,
  model?: string | null
): string {
  const b = (brand || "").trim();
  const m = (model || "").trim();
  if (!b) return m;
  if (!m) return b;
  if (m.toLowerCase().startsWith(b.toLowerCase())) {
    return m;
  }
  return `${b} ${m}`;
}

/**
 * Helper to determine if brand should be rendered alongside model in separated JSX blocks.
 */
export function shouldDisplayBrand(
  brand?: string | null,
  model?: string | null
): boolean {
  const b = (brand || "").trim();
  const m = (model || "").trim();
  if (!b) return false;
  if (!m) return true;
  return !m.toLowerCase().startsWith(b.toLowerCase());
}
