export function getCompanyLogoPath(companyName?: string | null): string | null {
  const n = (companyName || "").toLowerCase();
  if (!n) return null;
  if (n.includes("mmip") || n.includes("motor insurance pool")) return "/assets/companies/mmip.png";
  if (n.includes("kurnia")) return "/assets/companies/kurnia.png";
  if (n.includes("etiqa")) return "/assets/companies/etiqa.png";
  if (n.includes("amassurance") || n.includes("amgen") || n.includes("amgeneral")) {
    return "/assets/companies/amassurance.webp";
  }
  if (n.includes("sompo") || n.includes("berjaya")) return "/assets/companies/sompo.jpeg";
  if (n.includes("liberty")) return "/assets/companies/liberty.png";
  if (n.includes("lonpac")) return "/assets/companies/lonpac.png";
  if (n.includes("qbe")) return "/assets/companies/qbe.jpg";
  if (n.includes("takaful") && !n.includes("ikhlas")) return "/assets/companies/takaful.png";
  if (n.includes("tune")) return "/assets/companies/tune.png";
  return null;
}

export function formatTitleCaseInsurerName(companyName?: string | null): string {
  if (!companyName) return "Underwriter";
  const clean = companyName.trim();
  const lower = clean.toLowerCase();

  if (lower.includes("mmip") || lower.includes("motor insurance pool")) return "MMIP";
  if (lower.includes("allianz")) return "Allianz";
  if (lower.includes("etiqa") && lower.includes("takaful")) return "Etiqa Takaful";
  if (lower.includes("etiqa")) return "Etiqa";
  if (lower.includes("zurich") && lower.includes("takaful")) return "Zurich Takaful";
  if (lower.includes("zurich")) return "Zurich";
  if (lower.includes("lonpac")) return "Lonpac";
  if (lower.includes("berjaya") || lower.includes("sompo")) return "Berjaya Sompo";
  if (lower.includes("pacific") && lower.includes("orient")) return "Pacific & Orient";
  if (lower.includes("pacific")) return "Pacific";
  if (lower.includes("takaful malaysia") || lower.includes("syarikat takaful")) return "Takaful Malaysia";
  if (lower.includes("takaful ikhlas") || lower.includes("ikhlas")) return "Takaful Ikhlas";
  if (lower.includes("kurnia")) return "Kurnia";
  if (lower.includes("amgeneral") || lower.includes("amassurance") || lower.includes("amgen")) {
    return "AmAssurance";
  }
  if (lower.includes("chubb")) return "Chubb";
  if (lower.includes("msig")) return "MSIG";
  if (lower.includes("rhb")) return "RHB";
  if (lower.includes("liberty")) return "Liberty";
  if (lower.includes("tune")) return "Tune Protect";
  if (lower.includes("great eastern")) return "Great Eastern";
  if (lower.includes("aig")) return "AIG";
  if (lower.includes("generali") || lower.includes("axa")) return "Generali";
  if (lower.includes("progressive")) return "Progressive";
  if (lower.includes("tokio marine")) return "Tokio Marine";
  if (lower.includes("hong leong") || lower.includes("hla")) return "Hong Leong";

  const stripped = clean
    .replace(
      /\b(General Insurance Company|General Insurance|Insurance Company|Insurance Co\.?|Insurans|Insurance|Takaful|Berhad|Bhd\.?|Sdn\.? Bhd\.?|Corporation|Malaysia)\b/gi,
      ""
    )
    .replace(/[()]/g, "")
    .replace(/\s+/g, " ")
    .trim();

  const target = stripped || clean;
  return target
    .split(" ")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

export function getCompanyInitials(companyName?: string | null): string {
  const display = formatTitleCaseInsurerName(companyName);
  const words = display.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return `${words[0][0]}${words[1][0]}`.toUpperCase();
  }
  return display.slice(0, 2).toUpperCase() || "RL";
}
