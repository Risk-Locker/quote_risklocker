/**
 * Official Registered Corporate Names for Malaysian Insurers.
 * Grounded in official Bank Negara Malaysia (BNM) and General Insurance Association of Malaysia (PIAM) registries.
 */

export const OFFICIAL_INSURER_NAMES: Record<string, string> = {
  QBE: "QBE Insurance (Malaysia) Berhad",
  ETIQA: "Etiqa General Insurance Berhad",
  STMB: "Syarikat Takaful Malaysia Am Berhad",
  TAKAFUL_MALAYSIA: "Syarikat Takaful Malaysia Am Berhad",
  TAKAFUL: "Syarikat Takaful Malaysia Am Berhad",
  LONPAC: "Lonpac Insurance Bhd",
  BERJAYA_SOMPO: "Berjaya Sompo Insurance Berhad",
  SOMPO: "Berjaya Sompo Insurance Berhad",
  TUNE: "Tune Insurance Malaysia Berhad",
  TUNE_PROTECT: "Tune Insurance Malaysia Berhad",
  AMASSURANCE: "AmGeneral Insurance Berhad",
  AMGEN: "AmGeneral Insurance Berhad",
  AMGENERAL: "AmGeneral Insurance Berhad",
  KURNIA: "AmGeneral Insurance Berhad",
  ALLIANZ: "Allianz General Insurance Company (Malaysia) Berhad",
  ZURICH: "Zurich General Insurance Malaysia Berhad",
  AIG: "AIG Malaysia Insurance Berhad",
  CHUBB: "Chubb Insurance Malaysia Berhad",
  GENERALI: "Generali Insurance Malaysia Berhad",
  AXA: "Generali Insurance Malaysia Berhad",
  MSIG: "MSIG Insurance (Malaysia) Bhd",
  PACIFIC_ORIENT: "Pacific & Orient Insurance Co. Berhad",
  TOKIO_MARINE: "Tokio Marine Insurans (Malaysia) Berhad",
  RHB: "RHB Insurance Berhad",
  LIBERTY: "Liberty General Insurance Berhad",
};

/**
 * Normalizes any insurer code, raw string, or alias into its exact official registered legal corporate name.
 */
export function getOfficialInsurerName(rawName?: string | null): string {
  if (!rawName) return "QBE Insurance (Malaysia) Berhad";
  const upper = rawName.toUpperCase().replace(/[^A-Z0-9]/g, "_");
  
  // Direct match
  if (OFFICIAL_INSURER_NAMES[upper]) {
    return OFFICIAL_INSURER_NAMES[upper];
  }

  // Token / substring search
  for (const [key, official] of Object.entries(OFFICIAL_INSURER_NAMES)) {
    if (upper.includes(key)) {
      return official;
    }
  }

  return rawName.includes("Berhad") || rawName.includes("Bhd") ? rawName : `${rawName} Berhad`;
}

/**
 * Returns the short brand name used for section banners (e.g. "QBE", "Etiqa", "Lonpac").
 */
export function getInsurerShortName(rawName?: string | null): string {
  if (!rawName) return "QBE";
  const upper = rawName.toUpperCase();
  if (upper.includes("QBE")) return "QBE";
  if (upper.includes("ETIQA")) return "Etiqa";
  if (upper.includes("TAKAFUL") || upper.includes("STMB")) return "Takaful Malaysia";
  if (upper.includes("LONPAC")) return "Lonpac";
  if (upper.includes("SOMPO")) return "Berjaya Sompo";
  if (upper.includes("TUNE")) return "Tune Protect";
  if (upper.includes("AMASSURANCE") || upper.includes("AMGEN") || upper.includes("KURNIA")) return "AmAssurance";
  if (upper.includes("ALLIANZ")) return "Allianz";
  if (upper.includes("ZURICH")) return "Zurich";
  if (upper.includes("LIBERTY")) return "Liberty";
  if (upper.includes("MSIG")) return "MSIG";
  if (upper.includes("CHUBB")) return "Chubb";
  if (upper.includes("GENERALI") || upper.includes("AXA")) return "Generali";
  if (upper.includes("RHB")) return "RHB";
  return rawName.split(/[\s(]/)[0].trim() || "QBE";
}
