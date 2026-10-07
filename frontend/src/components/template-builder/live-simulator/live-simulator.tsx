"use client";

import { useMemo, useState } from "react";
import {
  Car,
  CheckCircle,
  CurrencyDollar,
  Lightning,
  Rows,
  Sparkle,
} from "@phosphor-icons/react";
import { CanvasElementView, type CanvasElement } from "@/components/template-canvas/shared";
import { computeAutoDensityPacking } from "@/lib/auto-density-packer";

interface LiveSimulatorProps {
  elements: CanvasElement[];
  assets: Array<{ id: string; label: string; url: string }>;
  config?: any;
}

export type ScenarioPreset = "compact_0_extras" | "standard_3_extras" | "heavy_10_extras" | "ev_saloon" | "ultra_33_benefits";

export function LiveSimulator({ elements, assets, config }: LiveSimulatorProps) {
  const [activeScenario, setActiveScenario] = useState<ScenarioPreset>("standard_3_extras");

  // Dynamic mock data tailored to the scenario
  const scenarioData = useMemo(() => {
    switch (activeScenario) {
      case "compact_0_extras":
        return {
          fields: {
            customer_name: "TAN JIA WEI",
            vehicle_no: "VAY 8821",
            insurance_company: "BERJAYA SOMPO INSURANCE BERHAD",
            coverage_type: "Comprehensive",
            cover_period: "01-11-2026 to 31-10-2027",
            car_model: "Honda City 1.5 V",
            engine_cc: "1498 cc",
            ncd_percent: "55.00%",
            valuation_type: "Market Value",
            authorized_driver: "All Driver",
            excess_amount: "RM 0.00",
            coverage_amount: "RM 68,000.00",
            premium: "1,248.50",
            roadtax: "90.00",
            service_fee: "0.00",
            total_amount: "1,338.50",
            valid_until: "30 Days",
            quotation_reference: "RL260000412",
          },
          extras: [],
          benefitCount: 6,
        };

      case "heavy_10_extras":
        return {
          fields: {
            customer_name: "LIM CHENG BOK (HOLDINGS) SDN. BHD.",
            vehicle_no: "WXY 9999",
            insurance_company: "BERJAYA SOMPO INSURANCE BERHAD",
            coverage_type: "Comprehensive",
            cover_period: "15-12-2026 to 14-12-2027",
            car_model: "Toyota Alphard 3.5 Executive Lounge",
            engine_cc: "3456 cc",
            ncd_percent: "0.00%",
            valuation_type: "Agreed Value",
            authorized_driver: "Named Driver",
            excess_amount: "RM 1,000.00",
            coverage_amount: "RM 380,000.00",
            premium: "7,842.10",
            roadtax: "2,460.00",
            service_fee: "0.00",
            total_amount: "12,452.10",
            valid_until: "14 Days",
            quotation_reference: "RL260000499",
          },
          extras: [
            { label: "Windscreen Damage Protection (RM 10,000)", price: { amount: 1500.0 } },
            { label: "Special Perils (Full Flood & Landslide)", price: { amount: 950.0 } },
            { label: "Legal Liability of Passengers (LLOP)", price: { amount: 7.5 } },
            { label: "Legal Liability to Passengers (LLTP)", price: { amount: 62.5 } },
            { label: "Driver & Passenger PA Protection (5 Seats)", price: { amount: 180.0 } },
            { label: "Spray Painting Whole Car", price: { amount: 350.0 } },
            { label: "Key Replacement Cover", price: { amount: 120.0 } },
            { label: "Cart / Daily Cash Allowance for Repairs", price: { amount: 200.0 } },
            { label: "Tyre & Rim Protection", price: { amount: 280.0 } },
            { label: "Unlimited Towing Extension", price: { amount: 300.0 } },
          ],
          benefitCount: 14,
        };

      case "ev_saloon":
        return {
          fields: {
            customer_name: "CHENG TECK KIONG",
            vehicle_no: "ANY 368",
            insurance_company: "BERJAYA SOMPO INSURANCE BERHAD",
            coverage_type: "Comprehensive",
            cover_period: "04-06-2026 to 03-06-2027",
            car_model: "Tesla Model 3 Performance",
            engine_cc: "9.4 kW",
            ncd_percent: "25.00%",
            valuation_type: "Market Value",
            authorized_driver: "All Driver",
            excess_amount: "RM 0.00",
            coverage_amount: "RM 199,000.00",
            premium: "4,419.01",
            roadtax: "40.00",
            service_fee: "0.00",
            total_amount: "4,673.21",
            valid_until: "30 Days",
            quotation_reference: "RL260000313",
          },
          extras: [
            { label: "Motorcycle PA Protection", price: { amount: 150.0 } },
            { label: "Legal Liability to Passengers (LLTP)", price: { amount: 56.7 } },
            { label: "Legal Liability of Passengers (LLOP)", price: { amount: 7.5 } },
          ],
          benefitCount: 8,
        };

      case "ultra_33_benefits":
        return {
          fields: {
            customer_name: "DATO SERI KHALID BIN HASSAN",
            vehicle_no: "BMW 740",
            insurance_company: "BERJAYA SOMPO INSURANCE BERHAD",
            coverage_type: "Comprehensive",
            cover_period: "01-01-2027 to 31-12-2027",
            car_model: "BMW 740Li xDrive M Sport",
            engine_cc: "2998 cc",
            ncd_percent: "55.00%",
            valuation_type: "Agreed Value",
            authorized_driver: "All Driver",
            excess_amount: "RM 0.00",
            coverage_amount: "RM 620,000.00",
            premium: "9,120.00",
            roadtax: "1,640.00",
            service_fee: "0.00",
            total_amount: "11,860.00",
            valid_until: "14 Days",
            quotation_reference: "RL260000999",
          },
          extras: [
            { label: "Executive Protection Package", price: { amount: 800.0 } },
            { label: "Special Perils & Natural Disasters", price: { amount: 300.0 } },
          ],
          benefitCount: 33,
        };

      case "standard_3_extras":
      default:
        return {
          fields: {
            customer_name: "CHENG TECK KIONG",
            vehicle_no: "ANY 368",
            insurance_company: "BERJAYA SOMPO INSURANCE BERHAD",
            coverage_type: "Comprehensive",
            cover_period: "04-06-2026 to 03-06-2027",
            car_model: "Tesla Model 3 Performance",
            engine_cc: "9.4 kW",
            ncd_percent: "25.00%",
            valuation_type: "Market Value",
            authorized_driver: "All Driver",
            excess_amount: "RM 0.00",
            coverage_amount: "RM 199,000.00",
            premium: "4,419.01",
            roadtax: "40.00",
            service_fee: "0.00",
            total_amount: "4,673.21",
            valid_until: "30 Days",
            quotation_reference: "RL260000313",
          },
          extras: [
            { label: "Motorcycle PA Protection", price: { amount: 150.0 } },
            { label: "Legal Liability to Passengers (LLTP)", price: { amount: 56.7 } },
            { label: "Legal Liability of Passengers (LLOP)", price: { amount: 7.5 } },
          ],
          benefitCount: 8,
        };
    }
  }, [activeScenario]);

  // Compute dynamic auto-density parameters
  const density = useMemo(() => {
    return computeAutoDensityPacking(scenarioData.benefitCount, 320);
  }, [scenarioData.benefitCount]);

  return (
    <div className="flex flex-col h-full bg-slate-100 overflow-hidden">
      {/* Scenario Switcher Toolbar */}
      <div className="bg-white border-b border-slate-200 p-2 flex items-center justify-between shrink-0 shadow-xs">
        <div className="flex items-center gap-1">
          <span className="text-[11px] font-bold text-slate-700 mr-2 uppercase tracking-wider flex items-center gap-1">
            <Sparkle size={13} className="text-red-600" />
            Live Scenario:
          </span>
          <button
            type="button"
            onClick={() => setActiveScenario("compact_0_extras")}
            className={`px-2 py-1 rounded text-xs font-semibold transition-all cursor-pointer ${
              activeScenario === "compact_0_extras"
                ? "bg-slate-900 text-white"
                : "bg-slate-100 hover:bg-slate-200 text-slate-700"
            }`}
          >
            0 Extras
          </button>
          <button
            type="button"
            onClick={() => setActiveScenario("standard_3_extras")}
            className={`px-2 py-1 rounded text-xs font-semibold transition-all cursor-pointer ${
              activeScenario === "standard_3_extras"
                ? "bg-slate-900 text-white"
                : "bg-slate-100 hover:bg-slate-200 text-slate-700"
            }`}
          >
            3 Extras (Standard)
          </button>
          <button
            type="button"
            onClick={() => setActiveScenario("heavy_10_extras")}
            className={`px-2 py-1 rounded text-xs font-semibold transition-all cursor-pointer ${
              activeScenario === "heavy_10_extras"
                ? "bg-slate-900 text-white"
                : "bg-slate-100 hover:bg-slate-200 text-slate-700"
            }`}
          >
            10 Extras (Heavy Table)
          </button>
          <button
            type="button"
            onClick={() => setActiveScenario("ev_saloon")}
            className={`px-2 py-1 rounded text-xs font-semibold transition-all cursor-pointer ${
              activeScenario === "ev_saloon"
                ? "bg-slate-900 text-white"
                : "bg-slate-100 hover:bg-slate-200 text-slate-700"
            }`}
          >
            EV Saloon (kW)
          </button>
          <button
            type="button"
            onClick={() => setActiveScenario("ultra_33_benefits")}
            className={`px-2 py-1 rounded text-xs font-semibold transition-all cursor-pointer ${
              activeScenario === "ultra_33_benefits"
                ? "bg-red-600 text-white"
                : "bg-red-50 hover:bg-red-100 text-red-700"
            }`}
          >
            33+ Benefits (Ultra Dense)
          </button>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono font-medium text-slate-500">
            A4 Budget: <strong className="text-emerald-700 font-bold">100% Clamped (1123px)</strong>
          </span>
          <span className="text-[10px] bg-slate-200/80 px-1.5 py-0.5 rounded font-mono font-semibold text-slate-700">
            {density.columns} Cols · {density.densityTier}
          </span>
        </div>
      </div>

      {/* Visual A4 Quotation Canvas Preview */}
      <div className="flex-1 overflow-auto p-4 flex justify-center items-start">
        <div
          className="bg-white shadow-xl rounded border border-slate-300 relative shrink-0"
          style={{
            width: 794,
            height: 1123,
            transformOrigin: "top center",
          }}
        >
          {elements.map((el) => (
            <CanvasElementView
              key={el.id}
              element={el}
              selected={false}
              readOnly={true}
              onPointerDown={() => {}}
              assets={assets as any}
              config={config}
              variableValues={scenarioData.fields}
              benefitData={{
                current_benefits: Array.from({ length: Math.min(scenarioData.benefitCount, 12) }).map((_, i) => ({
                  label: `Benefit ${i + 1}`,
                  value: "Included",
                  description: "Comprehensive roadside breakdown towing assistance.",
                })),
                available_addons: Array.from({ length: Math.max(0, scenarioData.benefitCount - 12) }).map((_, i) => ({
                  label: `Add-On ${i + 1}`,
                  value: "Optional",
                  description: "Special vehicle upgrade coverage.",
                })),
                extras: scenarioData.extras,
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
