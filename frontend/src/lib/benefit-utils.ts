/**
 * Benefit coverage formatting utilities.
 * Handles deterministic formatting for RM (Currency), KM (Distance / Unlimited), and Plain Text.
 */

export function formatBenefitCoverage(
  value: string | number | null | undefined,
  format?: "RM" | "KM" | "text" | string
): string {
  if (value === null || value === undefined) return "";
  const str = String(value).trim();
  if (!str) return "";

  const fmt = (format || "").toUpperCase();

  if (fmt === "RM") {
    // If string has numeric content or is just numbers (e.g. "55555" or "4000")
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

  if (fmt === "KM") {
    if (/unlimited/i.test(str)) {
      return "Unlimited KM";
    }
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
