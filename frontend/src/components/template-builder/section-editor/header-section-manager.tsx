"use client";

import React from "react";
import { ArrowUp, ArrowDown, ArrowsClockwise, Layout, Rows, TextT } from "@phosphor-icons/react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import type { SectionHeaderConfig } from "@/lib/template-section-compiler";

interface HeaderSectionManagerProps {
  header: SectionHeaderConfig;
  onChange: (updatedHeader: SectionHeaderConfig) => void;
}

const DEFAULT_ROWS: Array<"ref" | "vehicle" | "insurer"> = ["ref", "vehicle", "insurer"];

const ROW_LABELS: Record<"ref" | "vehicle" | "insurer", { title: string; defaultLabel: string; sampleVal: string }> = {
  ref: { title: "Quotation Reference", defaultLabel: "Quotation ref :", sampleVal: "RL260000334" },
  vehicle: { title: "Vehicle Number", defaultLabel: "Vehicle no. :", sampleVal: "JLY8828" },
  insurer: { title: "Insurer Company Name", defaultLabel: "Insurer :", sampleVal: "AMGENERAL INSURANCE BERHAD" },
};

export function HeaderSectionManager({ header, onChange }: HeaderSectionManagerProps) {
  const rowsOrder = header.rowsOrder || DEFAULT_ROWS;
  const insurerPosition = header.insurerPosition || "row3";
  const fontSize = header.fontSize ?? 10.5;

  const handleUpdate = (patch: Partial<SectionHeaderConfig>) => {
    onChange({
      ...header,
      ...patch,
    });
  };

  const handleMoveRow = (index: number, direction: -1 | 1) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= rowsOrder.length) return;
    const newOrder = [...rowsOrder];
    const temp = newOrder[index];
    newOrder[index] = newOrder[targetIndex];
    newOrder[targetIndex] = temp;
    handleUpdate({ rowsOrder: newOrder });
  };

  const handleSetInsurerPosition = (pos: "row3" | "top_left" | "row1") => {
    if (pos === "top_left") {
      handleUpdate({
        insurerPosition: "top_left",
        layout: "split_logo_insurer",
      });
    } else if (pos === "row1") {
      // Put insurer at top of order
      const remaining = rowsOrder.filter((r) => r !== "insurer");
      handleUpdate({
        insurerPosition: "row1",
        layout: "right_3_rows",
        rowsOrder: ["insurer", ...remaining],
      });
    } else {
      // Put insurer at bottom of order
      const remaining = rowsOrder.filter((r) => r !== "insurer");
      handleUpdate({
        insurerPosition: "row3",
        layout: "right_3_rows",
        rowsOrder: [...remaining, "insurer"],
      });
    }
  };

  const handleResetDefaults = () => {
    handleUpdate({
      layout: "right_3_rows",
      rowsOrder: ["ref", "vehicle", "insurer"],
      insurerPosition: "row3",
      refLabel: "Quotation Ref: ",
      vehicleLabel: "Vehicle No: ",
      insurerLabel: "Insurer: ",
      fontSize: 10.0,
      logoX: 40,
      logoY: 12,
      logoW: 88,
      logoH: 70,
    });
  };

  return (
    <div className="space-y-4 text-xs">
      {/* Header Overview Banner */}
      <div className="pb-3 border-b border-[var(--rl-border)] flex items-start justify-between">
        <div>
          <h4 className="text-sm font-bold text-[var(--rl-text-strong)] flex items-center gap-1.5">
            <Layout size={16} className="text-neutral-600" />
            Quotation Header Architecture
          </h4>
          <p className="text-xs text-[var(--rl-text-muted)] mt-0.5">
            Manage Risklocker logo positioning, insurer name placement, and extreme right metadata rows.
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={handleResetDefaults}
          className="text-[11px] h-7 px-2 text-neutral-600 hover:text-black flex items-center gap-1"
          title="Reset to 3-Row Standard"
        >
          <ArrowsClockwise size={12} />
          Reset
        </Button>
      </div>

      {/* Insurer Company Name Placement Mode */}
      <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3.5 space-y-3">
        <div className="flex items-center justify-between">
          <label className="font-bold text-[var(--rl-text-strong)] text-xs uppercase tracking-wider text-neutral-500">
            Insurer Company Name Placement
          </label>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200">
            Single-Line Guarantee
          </span>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <button
            type="button"
            onClick={() => handleSetInsurerPosition("row3")}
            className={`p-2.5 rounded-lg border text-left transition-all ${
              insurerPosition === "row3"
                ? "bg-neutral-900 text-white border-neutral-900 shadow-sm"
                : "bg-white text-neutral-700 border-neutral-200 hover:border-neutral-300"
            }`}
          >
            <div className="font-bold text-[11px]">Extreme Right (Row 3)</div>
            <div className={`text-[10px] mt-0.5 ${insurerPosition === "row3" ? "text-neutral-300" : "text-neutral-500"}`}>
              Below Vehicle No. (Standard)
            </div>
          </button>

          <button
            type="button"
            onClick={() => handleSetInsurerPosition("row1")}
            className={`p-2.5 rounded-lg border text-left transition-all ${
              insurerPosition === "row1"
                ? "bg-neutral-900 text-white border-neutral-900 shadow-sm"
                : "bg-white text-neutral-700 border-neutral-200 hover:border-neutral-300"
            }`}
          >
            <div className="font-bold text-[11px]">Extreme Right (Row 1)</div>
            <div className={`text-[10px] mt-0.5 ${insurerPosition === "row1" ? "text-neutral-300" : "text-neutral-500"}`}>
              Above Quotation Ref
            </div>
          </button>

          <button
            type="button"
            onClick={() => handleSetInsurerPosition("top_left")}
            className={`p-2.5 rounded-lg border text-left transition-all ${
              insurerPosition === "top_left"
                ? "bg-neutral-900 text-white border-neutral-900 shadow-sm"
                : "bg-white text-neutral-700 border-neutral-200 hover:border-neutral-300"
            }`}
          >
            <div className="font-bold text-[11px]">Top Left (Below Logo)</div>
            <div className={`text-[10px] mt-0.5 ${insurerPosition === "top_left" ? "text-neutral-300" : "text-neutral-500"}`}>
              Beside agency branding
            </div>
          </button>
        </div>
      </div>

      {/* Row Order Customizer */}
      {insurerPosition !== "top_left" && (
        <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3.5 space-y-3">
          <div className="flex items-center justify-between">
            <label className="font-bold text-[var(--rl-text-strong)] text-xs uppercase tracking-wider text-neutral-500 flex items-center gap-1.5">
              <Rows size={14} />
              Extreme Right Stack Order
            </label>
            <span className="text-[10px] text-neutral-500 font-medium">
              3 Rows · 18px Row Pitch
            </span>
          </div>

          <div className="space-y-1.5">
            {rowsOrder.map((rowKey, idx) => {
              const meta = ROW_LABELS[rowKey];
              const isFirst = idx === 0;
              const isLast = idx === rowsOrder.length - 1;

              return (
                <div
                  key={rowKey}
                  className="flex items-center justify-between p-2 rounded-lg bg-white border border-neutral-200 hover:border-neutral-300 transition-all"
                >
                  <div className="flex items-center gap-2.5">
                    <span className="size-5 rounded-full bg-neutral-100 text-neutral-700 font-mono text-[10px] font-bold flex items-center justify-center shrink-0">
                      {idx + 1}
                    </span>
                    <div>
                      <div className="font-bold text-[11px] text-neutral-900">
                        {meta.title}
                      </div>
                      <div className="text-[10px] text-neutral-400 font-mono">
                        {rowKey === "ref" && (header.refLabel || meta.defaultLabel)}
                        {rowKey === "vehicle" && (header.vehicleLabel || meta.defaultLabel)}
                        {rowKey === "insurer" && (header.insurerLabel || meta.defaultLabel)} {meta.sampleVal}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={isFirst}
                      onClick={() => handleMoveRow(idx, -1)}
                      className="p-1 rounded hover:bg-neutral-100 disabled:opacity-30 disabled:pointer-events-none text-neutral-600"
                      title="Move up"
                    >
                      <ArrowUp size={13} weight="bold" />
                    </button>
                    <button
                      type="button"
                      disabled={isLast}
                      onClick={() => handleMoveRow(idx, 1)}
                      className="p-1 rounded hover:bg-neutral-100 disabled:opacity-30 disabled:pointer-events-none text-neutral-600"
                      title="Move down"
                    >
                      <ArrowDown size={13} weight="bold" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Label Text Editors & Typography */}
      <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3.5 space-y-3">
        <label className="block font-bold text-[var(--rl-text-strong)] text-xs uppercase tracking-wider text-neutral-500 flex items-center gap-1.5">
          <TextT size={14} />
          Header Labels & Typography
        </label>

        <div className="space-y-2.5">
          <div>
            <label className="block text-[11px] font-semibold text-neutral-700 mb-1">
              Quotation Reference Label
            </label>
            <Input
              value={header.refLabel ?? "Quotation ref :"}
              onChange={(e) => handleUpdate({ refLabel: e.target.value })}
              placeholder="e.g. Quotation ref :"
              className="text-xs h-8"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-neutral-700 mb-1">
              Vehicle Number Label
            </label>
            <Input
              value={header.vehicleLabel ?? "Vehicle no. :"}
              onChange={(e) => handleUpdate({ vehicleLabel: e.target.value })}
              placeholder="e.g. Vehicle no. :"
              className="text-xs h-8"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-neutral-700 mb-1">
              Insurer Company Name Label
            </label>
            <Input
              value={header.insurerLabel ?? "Insurer :"}
              onChange={(e) => handleUpdate({ insurerLabel: e.target.value })}
              placeholder="e.g. Insurer :"
              className="text-xs h-8"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-neutral-700 mb-1">
              Header Font Size (pt)
            </label>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={8}
                max={14}
                step={0.5}
                value={fontSize}
                onChange={(e) => handleUpdate({ fontSize: parseFloat(e.target.value) || 10.5 })}
                className="text-xs h-8 w-24"
              />
              <span className="text-[11px] text-neutral-500">
                Recommended: 10.5pt (fits long insurer names in 1 line)
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Logo Sizing & Geometry */}
      <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3.5 space-y-3">
        <label className="block font-bold text-[var(--rl-text-strong)] text-xs uppercase tracking-wider text-neutral-500">
          Risklocker Logo Geometry
        </label>

        <div className="grid grid-cols-2 gap-2.5">
          <div>
            <label className="block text-[10px] font-semibold text-neutral-600 mb-1">
              Width (px)
            </label>
            <Input
              type="number"
              value={header.logoW ?? 150}
              onChange={(e) => handleUpdate({ logoW: parseInt(e.target.value, 10) || 150 })}
              className="text-xs h-8"
            />
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-neutral-600 mb-1">
              Height (px)
            </label>
            <Input
              type="number"
              value={header.logoH ?? 48}
              onChange={(e) => handleUpdate({ logoH: parseInt(e.target.value, 10) || 48 })}
              className="text-xs h-8"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
