/**
 * Benefit coverage formatting utilities.
 * Handles deterministic formatting for RM (Currency), KM (Distance / Unlimited), and Plain Text.
 */

export function formatBenefitCoverage(
  value: string | number | null | undefined,
  format?: "RM" | "KM" | "text" | string,
  companyName?: string | null
): string {
  if (value === null || value === undefined) return "";
  const str = String(value).trim();
  if (!str) return "";

  // Guard: Underwriter-specific RM vs KM rules
  const comp = (companyName || "").toLowerCase().trim();
  const isRmCompany =
    comp.includes("qbe") ||
    comp.includes("lonpac") ||
    comp.includes("sompo") ||
    comp.includes("tune");

  // Universal Unlimited check
  if (/^unlimited(?:\s*(?:km|distance|mileage|towing|costs?))?$/i.test(str) || /tanpa had/i.test(str)) {
    return "Unlimited";
  }
  if (/^unlimited\s*[-–]\s*(?:driver\s*)?plan\s*\d+/i.test(str)) {
    return str;
  }

  // No towing check
  if (/no towing|without towing|not included|none|tiada|nil|^0(?:\.0+)?(?:\s*km)?$|^(?:rm|myr)\s*0(?:\.0+)?$/i.test(str)) {
    return "No Towing";
  }

  // Explicit user-entered KM limit always takes precedence over insurer defaults
  const explicitKmMatch = str.match(/^(\d+(?:\.\d+)?)\s*(?:km|kilometers?|kilometres?)$/i);
  if (explicitKmMatch) {
    return `${explicitKmMatch[1]} km`;
  }

  // Explicit user-entered RM limit (>= 50 or formatted) takes precedence
  const explicitRmMatch = str.match(/^(?:rm|myr)\s*([\d,]+(?:\.\d{1,2})?)$/i);
  if (explicitRmMatch) {
    const val = parseFloat(explicitRmMatch[1].replace(/,/g, ""));
    if (!Number.isNaN(val) && val > 0) {
      return `RM ${Math.round(val).toLocaleString("en-MY")}`;
    }
  }

  // Fallback safeguard ONLY when text is non-specific/ambiguous (never overriding explicit KM/RM above)
  if (isRmCompany) {
    if (/^standard$/i.test(str) || /^included$/i.test(str)) {
      if (comp.includes("qbe")) return "RM 500";
      if (comp.includes("lonpac")) return "RM 400";
      if (comp.includes("sompo")) return "Unlimited";
      if (comp.includes("tune")) return "RM 300";
    }
  }

  // Guard: Preserve percentage values (e.g. "0.20%", "15%") without prefixing RM
  if (/^\s*-?\d+(?:\.\d+)?\s*%\s*$/.test(str)) {
    return str.replace(/\s+/g, "");
  }

  // Guard: Preserve canonical Included / Not Included labels
  if (/^included$/i.test(str)) return "Included";
  if (/^(?:not\s+included|not\s+covered)$/i.test(str)) return "Not Included";

  // Guard: If value already contains RM / MYR, ALWAYS format as currency regardless of requested format
  if (/^(?:RM|MYR)\s*[\d,]+/i.test(str)) {
    const cleanStr = str.replace(/^(?:RM|MYR)\s*/i, "").trim();
    const cleanNum = cleanStr.replace(/,/g, "");
    const num = parseFloat(cleanNum);
    if (!isNaN(num) && /^-?\d+(?:\.\d+)?$/.test(cleanNum)) {
      return `RM ${num.toLocaleString("en-MY", { minimumFractionDigits: num % 1 === 0 ? 0 : 2, maximumFractionDigits: 2 })}`;
    }
    const match = str.match(/(\d+(?:,\d+)*(?:\.\d+)?)/);
    if (match) {
      const parsed = parseFloat(match[1].replace(/,/g, ""));
      if (!isNaN(parsed)) {
        return `RM ${parsed.toLocaleString("en-MY", { minimumFractionDigits: parsed % 1 === 0 ? 0 : 2, maximumFractionDigits: 2 })}`;
      }
    }
    return str;
  }

  const fmt = (format || "").toUpperCase();

  if (fmt === "RM" || isRmCompany) {
    const cleanStr = str.replace(/^(?:RM|MYR)\s*/i, "").trim();
    const cleanNum = cleanStr.replace(/,/g, "");
    const num = parseFloat(cleanNum);
    if (!isNaN(num) && /^-?\d+(?:\.\d+)?$/.test(cleanNum)) {
      return `RM ${num.toLocaleString("en-MY", { minimumFractionDigits: num % 1 === 0 ? 0 : 2, maximumFractionDigits: 2 })}`;
    }
    const match = str.match(/(\d+(?:,\d+)*(?:\.\d+)?)/);
    if (match) {
      const parsed = parseFloat(match[1].replace(/,/g, ""));
      if (!isNaN(parsed)) {
        return `RM ${parsed.toLocaleString("en-MY", { minimumFractionDigits: parsed % 1 === 0 ? 0 : 2, maximumFractionDigits: 2 })}`;
      }
    }
    if (isRmCompany) {
      if (comp.includes("qbe")) return "RM 500";
      if (comp.includes("lonpac")) return "RM 400";
      if (comp.includes("sompo")) return "Unlimited";
      if (comp.includes("tune")) return "RM 300";
    }
    return str;
  }

  if (fmt === "KM" || str.toLowerCase().endsWith("km") || /^\d+\s*km$/i.test(str)) {
    const match = str.match(/(\d+(?:,\d+)*(?:\.\d+)?)/);
    if (match) {
      const num = parseFloat(match[1].replace(/,/g, ""));
      if (!isNaN(num)) {
        return `${num.toLocaleString("en-MY")} KM`;
      }
    }
    return str.toLowerCase().endsWith("km") ? str : `${str} KM`;
  }

  // Raw plain text (no RM or KM)
  return str;
}

export function formatShortInsurerName(name?: string | null): string {
  if (!name) return "Underwriter";
  const clean = name.trim();
  const lower = clean.toLowerCase();

  if (lower.includes("mmip") || lower.includes("motor insurance pool")) return "MMIP";
  if (lower.includes("allianz")) return "ALLIANZ";
  if (lower.includes("etiqa") && lower.includes("takaful")) return "ETIQA TAKAFUL";
  if (lower.includes("etiqa")) return "ETIQA";
  if (lower.includes("zurich") && lower.includes("takaful")) return "ZURICH TAKAFUL";
  if (lower.includes("zurich")) return "ZURICH";
  if (lower.includes("lonpac")) return "LONPAC";
  if (lower.includes("berjaya") || lower.includes("sompo")) return "BERJAYA SOMPO";
  if (lower.includes("pacific") && lower.includes("orient")) return "PACIFIC & ORIENT";
  if (lower.includes("pacific")) return "PACIFIC";
  if (lower.includes("takaful malaysia") || lower.includes("syarikat takaful")) return "TAKAFUL MALAYSIA";
  if (lower.includes("takaful ikhlas") || lower.includes("ikhlas")) return "TAKAFUL IKHLAS";
  if (lower.includes("kurnia")) return "KURNIA";
  if (lower.includes("amgeneral") || lower.includes("amassurance") || lower.includes("amgen")) return "AMASSURANCE";
  if (lower.includes("chubb")) return "CHUBB";
  if (lower.includes("msig")) return "MSIG";
  if (lower.includes("rhb")) return "RHB";
  if (lower.includes("liberty")) return "LIBERTY";
  if (lower.includes("tune")) return "TUNE PROTECT";
  if (lower.includes("great eastern")) return "GREAT EASTERN";
  if (lower.includes("aig")) return "AIG";
  if (lower.includes("generali") || lower.includes("axa")) return "GENERALI";
  if (lower.includes("progressive")) return "PROGRESSIVE";
  if (lower.includes("tokio marine")) return "TOKIO MARINE";
  if (lower.includes("qbe")) return "QBE";
  if (lower.includes("hong leong") || lower.includes("hla")) return "HONG LEONG";

  return clean
    .replace(/\b(General Insurance Company|General Insurance|Insurance Company|Insurance Co\.?|Insurans|Insurance|Takaful|Berhad|Bhd\.?|Sdn\.? Bhd\.?|Corporation|Malaysia)\b/gi, "")
    .replace(/[()]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase() || clean.toUpperCase();
}
