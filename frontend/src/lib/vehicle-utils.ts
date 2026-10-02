/**
 * Utility helper to format vehicle display names with fallback to chassis numbers.
 */

export function getVehicleDisplayName(vehicleNo?: string | null, chassisNo?: string | null): string {
  if (vehicleNo && vehicleNo.trim() && vehicleNo !== "UNPLATED" && !vehicleNo.startsWith("CHASSIS:")) {
    return vehicleNo.trim();
  }
  if (chassisNo && chassisNo.trim()) {
    return `Chassis: ${chassisNo.trim()}`;
  }
  if (vehicleNo && vehicleNo.startsWith("CHASSIS:")) {
    return `Chassis: ${vehicleNo.replace("CHASSIS:", "").trim()}`;
  }
  return "No Plate (Blank)";
}
