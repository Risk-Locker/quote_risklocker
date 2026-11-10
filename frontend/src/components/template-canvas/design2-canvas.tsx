"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  buildUnifiedMatrixCards,
  extractFreeCoverageItems,
  formatAddonValue,
  type UnifiedAddonCard,
} from "@/lib/unified-addon-engine";
import { fileUrl } from "@/lib/api";
import { Design2BenefitIconSvg, FreeCoverageGiftSvg } from "./design2-icons";

export interface Design2CanvasProps {
  fields: Record<string, any>;
  currentBenefits?: any[];
  availableAddons?: any[];
  selectedIds?: Set<string> | string[];
  companyName?: string;
  assets?: Array<{ id: string; label: string; url: string }>;
  insurerLogoUrl?: string;
  includeSchedule?: boolean;
  width?: number;
  height?: number;
}

const FIELD_ALIASES: Record<string, string[]> = {
  customer_name: ["customer_name", "insured_name"],
  quotation_reference: ["quotation_reference", "quotation_ref", "quote_ref", "reference_no", "quote_no"],
  vehicle_no: ["vehicle_no", "vehicle_plate", "car_plate", "plate_no"],
  insurance_company: ["insurance_company", "company_name", "insurer_name"],
  car_model: ["car_model"],
  cover_period: ["cover_period"],
  coverage_type: ["coverage_type"],
  ncd_percent: ["ncd_percent", "ncd_percentage"],
  valuation_type: ["valuation_type", "valuation_basis", "sum_insured_type"],
  excess_amount: ["excess_amount", "policy_excess", "excess"],
  coverage_amount: ["coverage_amount", "sum_insured", "market_value", "agreed_value"],
  premium: ["premium", "coverage_premium", "basic_premium_vehicle"],
  roadtax: ["roadtax", "road_tax_amount"],
  runner_fee: ["runner_fee", "service_fee"],
  total_amount: ["total_amount", "total_premium_adjusted", "gross_premium"],
};

function getVal(fields: Record<string, any>, key: string, fallback: string = ""): string {
  const keys = FIELD_ALIASES[key] || [key];
  for (const k of keys) {
    const f = fields[k];
    const val = f && typeof f === "object" ? f.value : f;
    if (val !== undefined && val !== null && String(val).trim()) {
      const s = String(val).trim();
      return key === "quotation_reference" ? s.replace(/[\s\-:_/]+$/, "") : s;
    }
  }
  return fallback;
}

function formatMoney(val: any): string {
  if (val === undefined || val === null || val === "") return "RM 0.00";
  const s = String(val).trim();
  const clean = s.replace(/[^0-9.]/g, "");
  if (!clean) return "RM 0.00";
  const num = parseFloat(clean);
  return isNaN(num)
    ? `RM ${s}`
    : `RM ${num.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function getLocalCompanyLogoPath(insurer: string): string {
  const n = (insurer || "").toLowerCase();
  if (n.includes("etiqa")) return "/assets/companies/etiqa.png";
  if (n.includes("amassurance") || n.includes("amgen")) return "/assets/companies/amassurance.webp";
  if (n.includes("sompo")) return "/assets/companies/sompo.jpeg";
  if (n.includes("liberty")) return "/assets/companies/liberty.png";
  if (n.includes("lonpac")) return "/assets/companies/lonpac.png";
  if (n.includes("qbe")) return "/assets/companies/qbe.jpg";
  if (n.includes("takaful")) return "/assets/companies/takaful.png";
  if (n.includes("tune")) return "/assets/companies/tune.png";
  return "";
}

const trimmedLogoCache = new Map<string, string>();

/**
 * Non-destructively crops excessive transparent/white square padding from loaded
 * insurer logos (e.g., Takaful 600x600 DB blobs) on client canvas without touching DB assets.
 */
function useTrimmedLogoSrc(src: string): string {
  const [trimmed, setTrimmed] = useState<string>(() => (src && trimmedLogoCache.get(src)) || src);

  useEffect(() => {
    setTrimmed((src && trimmedLogoCache.get(src)) || src);
    if (!src || typeof window === "undefined") return;
    if (trimmedLogoCache.has(src)) return;

    let cancelled = false;
    const img = new Image();
    try {
      const parsed = new URL(src, window.location.origin);
      if (parsed.origin !== window.location.origin) {
        img.crossOrigin = "anonymous";
      }
    } catch {
      // Relative URL, same-origin
    }

    img.onload = () => {
      if (cancelled) return;
      const w = img.naturalWidth || 0;
      const h = img.naturalHeight || 0;
      if (w < 8 || h < 8) return;
      try {
        const probe = document.createElement("canvas");
        probe.width = w;
        probe.height = h;
        const pctx = probe.getContext("2d");
        if (!pctx) return;
        pctx.drawImage(img, 0, 0);
        const { data } = pctx.getImageData(0, 0, w, h);

        let minX = w;
        let minY = h;
        let maxX = -1;
        let maxY = -1;
        for (let y = 0; y < h; y++) {
          const rowOff = y * w * 4;
          for (let x = 0; x < w; x++) {
            const idx = rowOff + x * 4;
            const a = data[idx + 3];
            if (a > 20 && (data[idx] < 245 || data[idx + 1] < 245 || data[idx + 2] < 245)) {
              if (x < minX) minX = x;
              if (x > maxX) maxX = x;
              if (y < minY) minY = y;
              if (y > maxY) maxY = y;
            }
          }
        }
        if (maxX < minX || maxY < minY) return;
        const pad = 2;
        const x0 = Math.max(0, minX - pad);
        const y0 = Math.max(0, minY - pad);
        const x1 = Math.min(w, maxX + 1 + pad);
        const y1 = Math.min(h, maxY + 1 + pad);
        const bw = x1 - x0;
        const bh = y1 - y0;
        if (bw >= 0.92 * w && bh >= 0.92 * h) {
          trimmedLogoCache.set(src, src);
          return;
        }
        const out = document.createElement("canvas");
        out.width = bw;
        out.height = bh;
        const octx = out.getContext("2d");
        if (!octx) return;
        octx.drawImage(probe, x0, y0, bw, bh, 0, 0, bw, bh);
        const result = out.toDataURL("image/png");
        trimmedLogoCache.set(src, result);
        if (!cancelled) setTrimmed(result);
      } catch {
        // Fallback safely to original src if canvas read fails
      }
    };
    img.src = src;
    return () => {
      cancelled = true;
    };
  }, [src]);

  return trimmed || src;
}

function GreenTickSvg({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10" fill="#5ABA00" />
      <path d="m8.2 12.2 2.5 2.5 5-5.2" stroke="#FFF" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function Design2Footer({ whatsappQrSrc }: { whatsappQrSrc: string }) {
  return (
    <div
      style={{
        flex: "0 0 108px",
        height: "108px",
        background: "#E52320",
        color: "#FFFFFF",
        padding: "0 44px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        boxSizing: "border-box",
      }}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: "14.5px", fontWeight: 800, letterSpacing: "0.1px", lineHeight: 1.1 }}>
          RISKLOCKER SDN. BHD.
        </div>
        <div style={{ fontSize: "6.8px", fontWeight: 500, opacity: 0.92, marginTop: "2px", marginBottom: "6px" }}>
          202301041962(1535879-U)
        </div>
        <div style={{ fontSize: "11.2px", fontWeight: 500, display: "flex", alignItems: "center", gap: "6px", lineHeight: 1.3 }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style={{ flexShrink: 0 }}>
            <path d="M20 4H4c-1.1 0-1.99.9-1.99 2L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z" />
          </svg>
          <span>admin@risklocker.com</span>
        </div>
        <div style={{ fontSize: "11.2px", fontWeight: 500, display: "flex", alignItems: "center", gap: "6px", marginTop: "2px", lineHeight: 1.3 }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor" style={{ flexShrink: 0 }}>
            <path d="M4 21h16v-2h-1V9h-5V4H5v15H4v2zm3-15h5v13H7V6zm7 5h3v8h-3v-8zM9 8h1.5v2H9V8zm0 3.5h1.5v2H9v-2zm0 3.5h1.5v2H9v-2z" />
          </svg>
          <span>011 1011 6880 ( Office )</span>
        </div>
      </div>

      <div style={{ width: "1px", height: "46px", background: "rgba(255, 255, 255, 0.72)", flexShrink: 0 }} />

      <div style={{ fontSize: "11px", fontWeight: 600, lineHeight: 1.35, display: "flex", alignItems: "flex-start", gap: "7px" }}>
        <svg width="14" height="18" viewBox="0 0 24 24" fill="currentColor" style={{ flexShrink: 0, marginTop: "1px" }}>
          <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" />
        </svg>
        <div>
          No. 77-02, Jalan Setia Tropika 1/8,<br />
          Taman Setia Tropika,<br />
          81200 Johor Bahru, Johor.
        </div>
      </div>

      <div style={{ width: "1px", height: "46px", background: "rgba(255, 255, 255, 0.72)", flexShrink: 0 }} />

      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <img
          src={whatsappQrSrc}
          alt="WhatsApp QR"
          style={{ width: "64px", height: "64px", objectFit: "contain", display: "block", flexShrink: 0 }}
        />
        <div>
          <div style={{ fontSize: "10.5px", fontWeight: 800, lineHeight: 1.2 }}>
            Scan For<br />More Information
          </div>
          <div style={{ fontSize: "9px", fontWeight: 600, fontStyle: "italic", opacity: 0.96, marginTop: "3px" }}>
            Contact Us On Whatsapp
          </div>
        </div>
      </div>
    </div>
  );
}

export function Design2CanvasView({
  fields,
  currentBenefits = [],
  availableAddons = [],
  selectedIds,
  companyName,
  assets = [],
  insurerLogoUrl,
  includeSchedule = false,
  width = 794,
  height = 1123,
}: Design2CanvasProps) {
  const selSet = useMemo(() => {
    if (!selectedIds) return new Set<string>();
    return selectedIds instanceof Set ? selectedIds : new Set(selectedIds);
  }, [selectedIds]);

  const quoteRef = getVal(fields, "quotation_reference", "RL260000314");
  const vehPlate = getVal(fields, "vehicle_no", "ANY 368");
  const insurer = getVal(fields, "insurance_company", companyName || "ETIQA GENERAL INSURANCE BERHAD");
  const custName = getVal(fields, "customer_name", "CHENG TECK KIOING");
  const period = getVal(fields, "cover_period", "04-06-2026 TO 03-06-2027");
  const covType = getVal(fields, "coverage_type", "Comprehensive");
  const carModel = getVal(fields, "car_model", "Tesla Model 3 Performance");
  const ncd = getVal(fields, "ncd_percent", "25.00%");
  const valType = getVal(fields, "valuation_type", "Market Value");
  const excess = getVal(fields, "excess_amount", "0.00");
  const sumInsured = getVal(fields, "coverage_amount", "198000.00");

  const premium = getVal(fields, "premium", "5328.10");
  const roadtax = getVal(fields, "roadtax", "40.00");
  const runner = getVal(fields, "runner_fee", "0.00");
  const totalPayable = getVal(fields, "total_amount", "5447.30");

  const rtCombined = useMemo(() => {
    try {
      const r1 = parseFloat(String(roadtax).replace(/[^0-9.]/g, "") || "0");
      const r2 = parseFloat(String(runner).replace(/[^0-9.]/g, "") || "0");
      return `RM ${(r1 + r2).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    } catch {
      return formatMoney(roadtax);
    }
  }, [roadtax, runner]);

  const localCompanyLogo = useMemo(() => getLocalCompanyLogoPath(insurer), [insurer]);
  const effectiveInsurerLogo = useMemo(() => {
    if (insurerLogoUrl) return insurerLogoUrl.startsWith("/assets/") ? insurerLogoUrl : fileUrl(insurerLogoUrl);
    const found = assets.find((a) => a.label === "insurer_logo");
    if (found?.url) return found.url.startsWith("/assets/") ? found.url : fileUrl(found.url);
    return localCompanyLogo;
  }, [insurerLogoUrl, assets, localCompanyLogo]);
  const [rawLogoSrc, setRawLogoSrc] = useState(effectiveInsurerLogo);
  useEffect(() => {
    setRawLogoSrc(effectiveInsurerLogo);
  }, [effectiveInsurerLogo]);
  const logoSrc = useTrimmedLogoSrc(rawLogoSrc);

  const addonCards = useMemo(() => {
    return buildUnifiedMatrixCards(currentBenefits, availableAddons, selSet, 24);
  }, [currentBenefits, availableAddons, selSet]);

  const freeItems = useMemo(() => {
    const extracted = extractFreeCoverageItems(currentBenefits, 6);
    if (extracted.length > 0 || currentBenefits.length > 0) {
      return extracted;
    }
    return [
      { title: "Legal Defense Costs", description: "Reimburses court legal representation and defense fees up to RM2,000." },
      { title: "Emergency Towing Assistance", description: "24/7 accidental towing service to nearest approved repairer up to RM 200." },
      { title: "Drive-Less Save-More", description: "Cash rebate up to 30% of base premium for low annual mileage." },
      { title: "Child Car Safety Seat", description: "Reimburses replacement or repair of child safety seats in a crash." },
    ];
  }, [currentBenefits]);

  const ncdDisplay = ncd.includes("%") ? ncd : `${ncd}%`;
  const page1Cards = addonCards.slice(0, 24);
  const overflowCards = addonCards.slice(24);
  const showPage2 = includeSchedule || overflowCards.length > 0;
  const selectedScheduleRows = useMemo(() => {
    return [
      ...freeItems.map((fi) => ({
        title: fi.title,
        description: fi.description || "Standard underwriter complimentary coverage.",
        value: "",
        hint: "generic",
        badge: "INCLUDED FOC",
      })),
      ...addonCards
        .filter((c) => c.is_selected)
        .map((c) => ({
          title: c.title,
          description: c.description || "Included rider / selected upgrade.",
          value: c.value || "",
          hint: c.icon_hint || "generic",
          badge: "SELECTED",
        })),
    ];
  }, [freeItems, addonCards]);

  return (
    <div style={{ width: `${width}px`, display: "flex", flexDirection: "column", gap: "16px", background: "transparent" }}>
      {/* PAGE 1: Primary Motor Quotation Design 2 */}
      <div
        className="d2-page-preview"
        style={{
          width: `${width}px`,
          height: `${height}px`,
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#FFFFFF",
          color: "#0F172A",
          fontFamily: "'Be Vietnam Pro', -apple-system, BlinkMacSystemFont, Arial, sans-serif",
          boxSizing: "border-box",
          overflow: "hidden",
        }}
      >
        <div style={{ flex: "1 1 auto", minHeight: 0, padding: "30px 44px 12px 44px", display: "flex", flexDirection: "column" }}>
          {/* Header */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center" }}>
              <img
                src="/assets/brand/logo-horizontal-black.png"
                alt="RISK LOCKER"
                style={{ height: "46px", maxWidth: "215px", objectFit: "contain", display: "block" }}
              />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: "17.3px", fontWeight: 800, letterSpacing: "-0.3px", lineHeight: 1.15 }}>
                  <span style={{ color: "#535353", fontWeight: 700 }}>Motor Insurance</span>
                  <span style={{ color: "#94A3B8", fontWeight: 300, margin: "0 4px" }}>|</span>
                  <span style={{ color: "#E52320", fontWeight: 800 }}>Quotation</span>
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "auto auto",
                    justifyContent: "end",
                    columnGap: "6px",
                    rowGap: "1px",
                    marginTop: "3px",
                    fontSize: "8.6px",
                    lineHeight: 1.3,
                  }}
                >
                  <span style={{ fontWeight: 600, color: "#334155" }}>Quotation Ref :</span>
                  <span style={{ fontWeight: 700, color: "#010000" }}>{quoteRef}</span>
                  <span style={{ fontWeight: 600, color: "#334155" }}>Vehicle No :</span>
                  <span style={{ fontWeight: 700, color: "#010000" }}>{vehPlate}</span>
                  <span style={{ fontWeight: 600, color: "#334155" }}>Insurer :</span>
                  <span style={{ fontWeight: 700, color: "#010000", textTransform: "uppercase" }}>{insurer}</span>
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end" }}>
                {logoSrc ? (
                  <img
                    src={logoSrc}
                    alt={insurer}
                    onError={() => {
                      if (localCompanyLogo && rawLogoSrc !== localCompanyLogo) {
                        setRawLogoSrc(localCompanyLogo);
                      } else {
                        setRawLogoSrc("");
                      }
                    }}
                    style={{ maxHeight: "38px", maxWidth: "132px", width: "auto", height: "auto", objectFit: "contain", display: "block" }}
                  />
                ) : (
                  <div style={{ fontSize: "12px", fontWeight: 900, color: "#0F172A", textTransform: "uppercase" }}>
                    {insurer.split(" ")[0]}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Structural Hairline 1: Header Bottom Divider */}
          <div style={{ height: "1px", background: "#64748B", margin: "13px 0 16px 0", flexShrink: 0 }} />

          {/* Upper Section: 2 Columns separated by Vertical Center Hairline */}
          <div style={{ display: "flex", alignItems: "stretch" }}>
            {/* Left Column (Specs + Premium) */}
            <div style={{ flex: 1.02, paddingRight: "18px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontSize: "14px", fontWeight: 800, color: "#E52320", marginBottom: "6px", lineHeight: 1.2 }}>
                  Vehicle Information <span style={{ fontSize: "13px", fontWeight: 700, color: "#544F4E" }}>车辆资料</span>
                </div>
                {[
                  { label: "Customer / 客户姓名", val: custName },
                  { label: "Period Of Insurance / 保障期限", val: period },
                  { label: "Coverage Type / 保障种类", val: covType },
                  { label: "Car Model / 车型", val: carModel },
                  { label: "NCD / 无索偿折扣", val: ncdDisplay },
                  { label: "Valuation Type / 估价方式", val: valType },
                  { label: "Policy Excess / 自负额", val: formatMoney(excess) },
                  { label: "Vehicle Sum Insured / 车辆保额", val: formatMoney(sumInsured) },
                ].map((row, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: "flex",
                      alignItems: "flex-end",
                      fontSize: "9px",
                      padding: "6px 0 3.5px 0",
                      minHeight: "26.5px",
                      boxSizing: "border-box",
                    }}
                  >
                    <div style={{ width: "168px", whiteSpace: "nowrap", fontWeight: 500, color: "#1E293B", flexShrink: 0, paddingBottom: "2px" }}>
                      {row.label}
                    </div>
                    <div style={{ width: "14px", textAlign: "center", color: "#475569", flexShrink: 0, paddingBottom: "2px" }}>:</div>
                    <div
                      style={{
                        fontWeight: 700,
                        color: "#0F172A",
                        wordBreak: "break-word",
                        flexGrow: 1,
                        borderBottom: "1px solid #334155",
                        paddingBottom: "2px",
                        lineHeight: 1.2,
                      }}
                    >
                      {row.val}
                    </div>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: "18px" }}>
                <div style={{ fontSize: "14px", fontWeight: 800, color: "#E52320", marginBottom: "5px", lineHeight: 1.2 }}>
                  Premium Summary <span style={{ fontSize: "13px", fontWeight: 700, color: "#544F4E" }}>保费</span>
                </div>
                <div style={{ display: "flex", alignItems: "flex-end", fontSize: "9px", padding: "6px 0 3.5px 0", minHeight: "26.5px", boxSizing: "border-box" }}>
                  <div style={{ width: "168px", whiteSpace: "nowrap", fontWeight: 500, color: "#1E293B", flexShrink: 0, paddingBottom: "2px" }}>
                    Insurance Premium / 保费
                  </div>
                  <div style={{ width: "14px", textAlign: "center", color: "#475569", flexShrink: 0, paddingBottom: "2px" }}>:</div>
                  <div style={{ fontWeight: 700, color: "#0F172A", flexGrow: 1, borderBottom: "1px solid #334155", paddingBottom: "2px", lineHeight: 1.2 }}>
                    {formatMoney(premium)}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "flex-end", fontSize: "9px", padding: "6px 0 3.5px 0", minHeight: "26.5px", boxSizing: "border-box" }}>
                  <div style={{ width: "168px", whiteSpace: "nowrap", fontWeight: 500, color: "#1E293B", flexShrink: 0, paddingBottom: "2px" }}>
                    Roadtax and Runner Fee / 路税及服务费
                  </div>
                  <div style={{ width: "14px", textAlign: "center", color: "#475569", flexShrink: 0, paddingBottom: "2px" }}>:</div>
                  <div style={{ fontWeight: 700, color: "#0F172A", flexGrow: 1, borderBottom: "1px solid #334155", paddingBottom: "2px", lineHeight: 1.2 }}>
                    {rtCombined}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "baseline", gap: "8px", marginTop: "22px" }}>
                  <div style={{ fontSize: "13px", fontWeight: 800, color: "#E52320", whiteSpace: "nowrap" }}>TOTAL PAYABLE 应付总额 :</div>
                  <div style={{ fontSize: "21px", fontWeight: 900, color: "#E52320", letterSpacing: "-0.4px", lineHeight: 1, whiteSpace: "nowrap" }}>
                    {formatMoney(totalPayable)}
                  </div>
                </div>
              </div>
            </div>

            {/* Structural Hairline 2: Vertical Center Divider */}
            <div style={{ width: "1px", background: "#64748B", flexShrink: 0 }} />

            {/* Right Column: Unified Soft Grey Container (#F8F9FC) */}
            <div style={{ flex: 0.98, paddingLeft: "18px", display: "flex", flexDirection: "column" }}>
              <div
                style={{
                  flex: 1,
                  background: "#F8F9FC",
                  borderRadius: "10px",
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div
                    style={{
                      background: "#E52320",
                      color: "#FFFFFF",
                      height: "40px",
                      padding: "0 15px",
                      fontSize: "10.5px",
                      fontWeight: 800,
                      display: "flex",
                      alignItems: "center",
                      gap: "9px",
                    }}
                  >
                    <FreeCoverageGiftSvg width={28} height={24} />
                    <span>{insurer.split(" ")[0]} Free Added Coverage</span>
                  </div>
                  <div style={{ padding: "16px 15px 12px 15px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "14px 11px", alignContent: "start" }}>
                    {freeItems.length > 0 ? (
                      freeItems.map((fi, idx) => (
                        <div key={idx} style={{ display: "flex", alignItems: "flex-start", gap: "6px" }}>
                          <div style={{ flexShrink: 0, marginTop: "1px" }}>
                            <GreenTickSvg size={15} />
                          </div>
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: "8.5px", fontWeight: 700, color: "#0F172A", lineHeight: 1.15 }}>{fi.title}</div>
                            {fi.description && (
                              <div
                                style={{
                                  fontSize: "7.2px",
                                  color: "#52525B",
                                  lineHeight: 1.24,
                                  marginTop: "2px",
                                  overflow: "hidden",
                                  display: "-webkit-box",
                                  WebkitLineClamp: 3,
                                  WebkitBoxOrient: "vertical",
                                }}
                              >
                                {fi.description}
                              </div>
                            )}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div style={{ gridColumn: "1 / -1", fontSize: "8px", color: "#52525B" }}>
                        Standard comprehensive policy benefits included under underwriter terms.
                      </div>
                    )}
                  </div>
                </div>

                <div style={{ padding: "10px 14px 14px 14px", display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: "6px" }}>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontSize: "10.8px", fontWeight: 800, color: "#E52320", marginBottom: "4px", lineHeight: 1.2, whiteSpace: "nowrap" }}>
                      Company Bank Details <span style={{ fontSize: "9.8px", fontWeight: 700, color: "#544F4E" }}>公司银行戶口</span>
                    </div>
                    <div style={{ fontSize: "11.4px", fontWeight: 800, color: "#0F172A", lineHeight: 1.28 }}>RISKLOCKER SDN.BHD.</div>
                    <div style={{ fontSize: "11.2px", fontWeight: 400, color: "#1E293B", lineHeight: 1.28 }}>Hong Leong Bank</div>
                    <div style={{ fontSize: "11.4px", fontWeight: 400, color: "#1E293B", letterSpacing: "0.2px", lineHeight: 1.28 }}>12300318500</div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
                    <img
                      src="/assets/duitnow_badge.png"
                      alt="DuitNow"
                      style={{ height: "45px", width: "auto", objectFit: "contain", display: "block" }}
                    />
                    <div
                      style={{
                        position: "relative",
                        width: "68px",
                        height: "68px",
                        padding: "4px",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        flexShrink: 0,
                      }}
                    >
                      <svg style={{ position: "absolute", inset: 0, width: "68px", height: "68px", pointerEvents: "none" }} viewBox="0 0 68 68" fill="none">
                        <path d="M2 14V4C2 2.9 2.9 2 4 2H14" stroke="#E11D48" strokeWidth="2.2" strokeLinecap="round" />
                        <path d="M54 2H64C65.1 2 66 2.9 66 4V14" stroke="#E11D48" strokeWidth="2.2" strokeLinecap="round" />
                        <path d="M2 54V64C2 65.1 2.9 66 4 66H14" stroke="#E11D48" strokeWidth="2.2" strokeLinecap="round" />
                        <path d="M54 66H64C65.1 66 66 65.1 66 64V54" stroke="#E11D48" strokeWidth="2.2" strokeLinecap="round" />
                      </svg>
                      <img
                        src="/assets/duitnow_qr.jpeg"
                        alt="DuitNow QR"
                        style={{ width: "58px", height: "58px", objectFit: "contain", display: "block" }}
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Structural Hairline 3: Mid-Page Horizontal Divider */}
          <div style={{ height: "1px", background: "#64748B", margin: "18px 0 12px 0", flexShrink: 0 }} />

          {/* Lower Section: Add-On Upgrades ++ */}
          <div style={{ flex: "1 1 auto", minHeight: 0, display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "11px" }}>
              <div style={{ fontSize: "24.5px", fontWeight: 900, letterSpacing: "-0.4px", lineHeight: 1 }}>
                <span style={{ color: "#E52320" }}>Add-On</span>{" "}
                <span style={{ color: "#1D1D1B" }}>Upgrades</span>{" "}
                <span style={{ color: "#E52320" }}>++</span>
              </div>
              <div style={{ fontSize: "11.2px", fontWeight: 700, fontStyle: "italic", color: "#353331", letterSpacing: "0.2px", textTransform: "uppercase" }}>
                ADDITIONAL PROTECTION FOR GREATER PEACE OF MIND
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "7px 7px" }}>
              {page1Cards.map((card: UnifiedAddonCard) => (
                <div
                  key={card.id}
                  style={{
                    borderRadius: "6px",
                    background: "#F8F9FC",
                    boxShadow: "0 1px 2px rgba(15, 23, 42, 0.045)",
                    display: "flex",
                    alignItems: "stretch",
                    height: "66px",
                    boxSizing: "border-box",
                    overflow: "hidden",
                  }}
                >
                  <div style={{ flex: "0 0 38px", display: "flex", alignItems: "center", justifyContent: "center", paddingLeft: "3px" }}>
                    <Design2BenefitIconSvg hint={card.icon_hint} size={38} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0, padding: "4.5px 5.5px 4.5px 2px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                    <div style={{ minHeight: 0 }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "3px" }}>
                        <div
                          style={{
                            fontSize: "7.05px",
                            fontWeight: 700,
                            color: "#0F172A",
                            lineHeight: 1.13,
                            paddingTop: "2px",
                            overflow: "hidden",
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                          }}
                        >
                          {card.title}
                        </div>
                        <div style={{ fontSize: "6.1px", fontWeight: 600, color: "#94A3B8", flexShrink: 0, lineHeight: 1 }}>
                          {card.serial_number}
                        </div>
                      </div>
                      {card.value && (
                        <div style={{ fontSize: "6.9px", fontWeight: 800, color: "#16A34A", marginTop: "1px", lineHeight: 1.1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {card.value}
                        </div>
                      )}
                      {card.description && (
                        <div
                          style={{
                            fontSize: "6.05px",
                            color: "#475569",
                            lineHeight: 1.16,
                            marginTop: "1px",
                            overflow: "hidden",
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                          }}
                        >
                          {card.description}
                        </div>
                      )}
                    </div>
                    <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
                      {card.is_selected ? (
                        <GreenTickSvg size={14} />
                      ) : (
                        <div style={{ width: "10.5px", height: "10.5px", border: "1.8px solid #677184", borderRadius: "1.5px", background: "#FFFFFF" }} />
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
            {overflowCards.length > 0 && (
              <div style={{ fontSize: "6.8px", fontWeight: 700, color: "#E52320", marginTop: "4px", textAlign: "right" }}>
                + {overflowCards.length} additional add-ons &amp; full terms continued on Sheet 2 &rarr;
              </div>
            )}
          </div>
        </div>

        <Design2Footer whatsappQrSrc="/assets/whatsapp_qr.png" />
      </div>

      {/* PAGE 2: Overflow Continuation & Detailed Benefits Schedule */}
      {showPage2 && (
        <div
          className="d2-page-preview"
          style={{
            width: `${width}px`,
            height: `${height}px`,
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            background: "#FFFFFF",
            color: "#0F172A",
            fontFamily: "'Be Vietnam Pro', -apple-system, BlinkMacSystemFont, Arial, sans-serif",
            boxSizing: "border-box",
            overflow: "hidden",
            boxShadow: "0 4px 14px rgba(0,0,0,0.08)",
          }}
        >
          <div style={{ flex: "1 1 auto", minHeight: 0, padding: "28px 44px 16px 44px", display: "flex", flexDirection: "column" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px", borderBottom: "1.5px solid #E2E8F0", paddingBottom: "8px" }}>
              <img src="/assets/brand/logo-horizontal-black.png" alt="RISK LOCKER" style={{ height: "30px", maxWidth: "150px", objectFit: "contain" }} />
              <div style={{ textAlign: "right", flexGrow: 1, padding: "0 12px" }}>
                <div style={{ fontSize: "13px", fontWeight: 900 }}>
                  <span style={{ color: "#0F172A" }}>Benefits &amp; Endorsements Schedule</span>
                  <span style={{ color: "#E52320" }}> | {quoteRef}</span>
                </div>
                <div style={{ fontSize: "8px", fontWeight: 600, color: "#475569", marginTop: "2px" }}>
                  Client: <strong style={{ color: "#0F172A" }}>{custName}</strong> · Vehicle: <strong style={{ color: "#0F172A" }}>{vehPlate}</strong> · Sheet 2
                </div>
              </div>
              {logoSrc && (
                <img src={logoSrc} alt={insurer} style={{ maxHeight: "30px", maxWidth: "98px", width: "auto", height: "auto", objectFit: "contain" }} />
              )}
            </div>

            {overflowCards.length > 0 && (
              <div style={{ marginBottom: "10px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #64748B", paddingBottom: "3px", marginBottom: "7px" }}>
                  <div style={{ fontSize: "11px", fontWeight: 900, color: "#E52320" }}>
                    Add-On Upgrades <span style={{ color: "#1E293B" }}>++</span>{" "}
                    <span style={{ fontSize: "9.5px", color: "#64748B", fontWeight: 700 }}>
                      (Continued Slots {overflowCards[0].serial_number}–{overflowCards[overflowCards.length - 1].serial_number})
                    </span>
                  </div>
                  <div style={{ fontSize: "7.2px", fontWeight: 700, fontStyle: "italic", color: "#353331" }}>EXTENDED COVERAGE OPTIONS</div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "7px 8px" }}>
                  {overflowCards.map((card) => (
                    <div
                      key={card.id}
                      style={{
                        background: "#F8F9FC",
                        borderRadius: "6px",
                        boxShadow: "0 1px 2px rgba(15, 23, 42, 0.05)",
                        height: "62px",
                        display: "flex",
                        alignItems: "stretch",
                        overflow: "hidden",
                      }}
                    >
                      <div style={{ flex: "0 0 40px", display: "flex", alignItems: "center", justifyContent: "center", paddingLeft: "4px" }}>
                        <Design2BenefitIconSvg hint={card.icon_hint} size={36} />
                      </div>
                      <div style={{ flex: 1, minWidth: 0, padding: "4px 7px 4px 2px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                        <div>
                          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "3px" }}>
                            <div style={{ fontSize: "7.4px", fontWeight: 700, color: "#0F172A", lineHeight: 1.12, paddingTop: "2px", overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                              {card.title}
                            </div>
                            <div style={{ fontSize: "6.2px", fontWeight: 600, color: "#94A3B8", flexShrink: 0, lineHeight: 1 }}>
                              {card.serial_number}
                            </div>
                          </div>
                          {card.value && (
                            <div style={{ fontSize: "7px", fontWeight: 800, color: "#16A34A", marginTop: "1px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                              {card.value}
                            </div>
                          )}
                          {card.description && (
                            <div style={{ fontSize: "6.2px", color: "#475569", lineHeight: 1.15, marginTop: "1px", overflow: "hidden", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>
                              {card.description}
                            </div>
                          )}
                        </div>
                        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center" }}>
                          {card.is_selected ? (
                            <GreenTickSvg size={14} />
                          ) : (
                            <div style={{ width: "10.5px", height: "10.5px", border: "1.8px solid #677184", borderRadius: "1.5px", background: "#FFF" }} />
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ marginBottom: "10px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1.5px solid #0F172A", paddingBottom: "3px", marginBottom: "6px" }}>
                <div style={{ fontSize: "11px", fontWeight: 900, color: "#0F172A" }}>
                  Active Coverages &amp; Selected Endorsements <span style={{ color: "#E52320" }}>({selectedScheduleRows.length})</span>
                </div>
                <div style={{ fontSize: "7px", fontWeight: 700, color: "#64748B" }}>FULL POLICY TERMS &amp; LIMITS</div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "5px 8px" }}>
                {selectedScheduleRows.slice(0, 12).map((row, idx) => (
                  <div key={idx} style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "8px", padding: "6px 8px", border: "1px solid #E2E8F0", borderRadius: "6px", background: "#FFF" }}>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "8px", minWidth: 0, flex: 1 }}>
                      <div style={{ width: "26px", height: "26px", borderRadius: "5px", background: "#F8F9FC", border: "1px solid #E2E8F0", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        <Design2BenefitIconSvg hint={row.hint} size={20} />
                      </div>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: "8.8px", fontWeight: 800, color: "#0F172A" }}>
                          {row.title} {formatAddonValue(row.value) && <span style={{ color: "#16A34A", fontSize: "7.8px" }}>({formatAddonValue(row.value)})</span>}
                        </div>
                        <div style={{ fontSize: "7.2px", color: "#475569", lineHeight: 1.25, marginTop: "1px" }}>{row.description}</div>
                      </div>
                    </div>
                    <span style={{ fontSize: "6.8px", fontWeight: 800, padding: "2px 6px", borderRadius: "4px", whiteSpace: "nowrap", background: "#ECFDF5", color: "#15803D", border: "1px solid #A7F3D0" }}>
                      {row.badge}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {(() => {
              const optionalCards = addonCards.filter((c) => !c.is_selected);
              const overflowGridRows = overflowCards.length > 0 ? Math.ceil(overflowCards.length / 4) : 0;
              const overflowH = overflowGridRows * 69 + (overflowCards.length > 0 ? 34 : 0);
              const activeGridRows = selectedScheduleRows.length > 0 ? Math.ceil(Math.min(selectedScheduleRows.length, 12) / 2) : 0;
              const activeH = activeGridRows * 46 + (selectedScheduleRows.length > 0 ? 32 : 0);
              const remainingBudget = Math.max(0, 875 - overflowH - activeH - 28);
              const optLimit = Math.max(0, Math.floor(remainingBudget / 38) * 2);
              const optSlice = optionalCards.slice(0, optLimit);
              if (optSlice.length === 0) return null;
              return (
                <div style={{ marginBottom: "6px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #CBD5E1", paddingBottom: "2px", marginBottom: "5px" }}>
                    <div style={{ fontSize: "10px", fontWeight: 800, color: "#334155" }}>
                      Optional Add-On Upgrades Reference <span style={{ fontWeight: 600, color: "#64748B" }}>({optionalCards.length} Available)</span>
                    </div>
                    <div style={{ fontSize: "6.8px", fontWeight: 700, color: "#94A3B8" }}>ASK YOUR ADVISOR TO INCLUDE ANY RIDER</div>
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 8px" }}>
                    {optSlice.map((oc) => (
                      <div key={oc.id} style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "6px", padding: "4px 7px", border: "1px solid #F1F5F9", borderRadius: "5px", background: "#F8FAFC" }}>
                        <div style={{ display: "flex", alignItems: "flex-start", gap: "6px", minWidth: 0, flex: 1 }}>
                          <div style={{ flexShrink: 0, marginTop: "1px" }}>
                            <Design2BenefitIconSvg hint={oc.icon_hint} size={18} />
                          </div>
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: "7.8px", fontWeight: 700, color: "#0F172A" }}>
                              {oc.serial_number} · {oc.title} {formatAddonValue(oc.value) && <span style={{ color: "#16A34A" }}>({formatAddonValue(oc.value)})</span>}
                            </div>
                            {oc.description && <div style={{ fontSize: "6.6px", color: "#64748B", lineHeight: 1.25 }}>{oc.description}</div>}
                          </div>
                        </div>
                        <span style={{ fontSize: "6.4px", fontWeight: 700, padding: "1.5px 4.5px", borderRadius: "3px", whiteSpace: "nowrap", background: "#F8FAFC", color: "#475569", border: "1px solid #E2E8F0" }}>
                          OPTIONAL
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })()}
          </div>

          <Design2Footer whatsappQrSrc="/assets/whatsapp_qr.png" />
        </div>
      )}
    </div>
  );
}
