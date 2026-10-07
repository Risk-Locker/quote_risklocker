"use client";

import { useState } from "react";
import {
  BracketsCurly,
  CodeSimple,
  PaintBrush,
  SlidersHorizontal,
  TreeStructure,
} from "@phosphor-icons/react";
import type { BlockTree, TemplateBlock } from "@/lib/template-block-engine";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

interface BlockInspectorProps {
  tree: BlockTree;
  selectedBlockId: string | null;
  onSelectBlock: (id: string) => void;
  onUpdateBlock: (blockId: string, updates: Partial<TemplateBlock>) => void;
}

const VARIABLE_OPTIONS = [
  { id: "customer_name", label: "Customer Name" },
  { id: "vehicle_no", label: "Vehicle Number" },
  { id: "insurance_company", label: "Insurer Name" },
  { id: "coverage_type", label: "Coverage Type" },
  { id: "cover_period", label: "Cover Period" },
  { id: "car_model", label: "Car Model" },
  { id: "engine_cc", label: "Engine Capacity" },
  { id: "ncd_percent", label: "NCD %" },
  { id: "valuation_type", label: "Valuation Type" },
  { id: "authorized_driver", label: "Authorised Driver (All / Named)" },
  { id: "excess_amount", label: "Policy Excess" },
  { id: "compulsory_excess", label: "Compulsory Excess" },
  { id: "coverage_amount", label: "Vehicle Sum Insured" },
  { id: "premium", label: "Insurance Premium" },
  { id: "roadtax", label: "Roadtax and Runner Fee" },
  { id: "total_amount", label: "Total Payable" },
  { id: "valid_until", label: "Validity Date" },
  { id: "quotation_reference", label: "Quotation Reference" },
];

export function BlockInspector({
  tree,
  selectedBlockId,
  onSelectBlock,
  onUpdateBlock,
}: BlockInspectorProps) {
  const [activeTab, setActiveTab] = useState<"details" | "css" | "structure">("details");

  // Find selected block in tree
  let selectedBlock: TemplateBlock | null = null;
  for (const sec of tree.sections) {
    for (const cont of sec.containers) {
      for (const b of cont.blocks) {
        if (b.id === selectedBlockId) {
          selectedBlock = b;
          break;
        }
      }
    }
  }

  return (
    <aside className="w-80 border-l border-[var(--rl-border)] bg-white flex flex-col h-full select-none">
      {/* 3-Tab Header */}
      <div className="border-b border-[var(--rl-border)] bg-slate-50 flex items-center p-1 gap-1">
        <button
          type="button"
          onClick={() => setActiveTab("details")}
          className={`flex-1 py-1.5 px-2 rounded text-[11px] font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
            activeTab === "details"
              ? "bg-white text-slate-900 shadow-xs border border-slate-200"
              : "text-slate-600 hover:text-slate-800"
          }`}
        >
          <SlidersHorizontal size={13} weight="bold" />
          Details
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("css")}
          className={`flex-1 py-1.5 px-2 rounded text-[11px] font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
            activeTab === "css"
              ? "bg-white text-slate-900 shadow-xs border border-slate-200"
              : "text-slate-600 hover:text-slate-800"
          }`}
        >
          <PaintBrush size={13} weight="bold" />
          CSS / Style
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("structure")}
          className={`flex-1 py-1.5 px-2 rounded text-[11px] font-bold flex items-center justify-center gap-1.5 transition-all cursor-pointer ${
            activeTab === "structure"
              ? "bg-white text-slate-900 shadow-xs border border-slate-200"
              : "text-slate-600 hover:text-slate-800"
          }`}
        >
          <TreeStructure size={13} weight="bold" />
          Structure
        </button>
      </div>

      {/* Tab 1: Details & Data Binding */}
      {activeTab === "details" && (
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {!selectedBlock ? (
            <div className="text-center py-10 text-slate-600 text-xs">
              Select an element or container on the canvas to configure data binding.
            </div>
          ) : (
            <div className="space-y-3.5">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-600">
                  Block: {selectedBlock.type}
                </span>
                <span className="text-[10px] font-mono text-slate-600">{selectedBlock.id}</span>
              </div>

              {/* Variable with Title Binding */}
              {selectedBlock.type === "variable_with_title" && (
                <>
                  <label className="block text-xs font-semibold text-slate-700">
                    Title / Prefix Label
                    <Input
                      className="mt-1 text-xs"
                      value={selectedBlock.title || ""}
                      onChange={(e) => onUpdateBlock(selectedBlock!.id, { title: e.target.value } as any)}
                    />
                  </label>
                  <label className="block text-xs font-semibold text-slate-700">
                    Bound Variable
                    <Select
                      className="mt-1 text-xs"
                      value={selectedBlock.variableId || ""}
                      onChange={(e) => onUpdateBlock(selectedBlock!.id, { variableId: e.target.value } as any)}
                    >
                      {VARIABLE_OPTIONS.map((opt) => (
                        <option key={opt.id} value={opt.id}>
                          {opt.label} ({opt.id})
                        </option>
                      ))}
                    </Select>
                  </label>
                </>
              )}

              {/* Standalone Variable Binding */}
              {selectedBlock.type === "variable" && (
                <label className="block text-xs font-semibold text-slate-700">
                  Bound Variable
                  <Select
                    className="mt-1 text-xs"
                    value={selectedBlock.variableId || ""}
                    onChange={(e) => onUpdateBlock(selectedBlock!.id, { variableId: e.target.value } as any)}
                  >
                    {VARIABLE_OPTIONS.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.label} ({opt.id})
                      </option>
                    ))}
                  </Select>
                </label>
              )}

              {/* Static Text */}
              {selectedBlock.type === "text" && (
                <label className="block text-xs font-semibold text-slate-700">
                  Text Content
                  <Input
                    className="mt-1 text-xs"
                    value={selectedBlock.text || ""}
                    onChange={(e) => onUpdateBlock(selectedBlock!.id, { text: e.target.value } as any)}
                  />
                </label>
              )}

              {/* Image Block Slot */}
              {selectedBlock.type === "image" && (
                <label className="block text-xs font-semibold text-slate-700">
                  Asset Slot
                  <Select
                    className="mt-1 text-xs"
                    value={selectedBlock.assetSlot || "bank_qr_layout_dark"}
                    onChange={(e) => onUpdateBlock(selectedBlock!.id, { assetSlot: e.target.value } as any)}
                  >
                    <option value="bank_qr_layout_dark">Bank QR Layout (Dark) - assets/bank_qr_layout_dark.jpg</option>
                    <option value="risklocker_logo">RiskLocker Logo</option>
                    <option value="insurer_logo">Insurer Logo</option>
                    <option value="qr_code">DuitNow QR Code</option>
                  </Select>
                </label>
              )}

              {/* Specs Table Block */}
              {selectedBlock.type === "specs_table" && (
                <div className="space-y-2">
                  <p className="text-xs font-bold text-slate-700">Active Specs Rows (10)</p>
                  <div className="space-y-1 max-h-56 overflow-y-auto border border-slate-200 rounded p-1.5 bg-slate-50">
                    {selectedBlock.rows.map((r, i) => (
                      <div key={r.id} className="text-[11px] p-1 bg-white rounded border border-slate-100 flex items-center justify-between">
                        <span className="font-medium text-slate-700 truncate">{r.label}</span>
                        <span className="font-mono text-[10px] text-red-600 shrink-0">{r.variableId}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: CSS / Styling */}
      {activeTab === "css" && (
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {!selectedBlock ? (
            <div className="text-center py-10 text-slate-600 text-xs">
              Select an element to view and adjust style properties.
            </div>
          ) : (
            <div className="space-y-3">
              <label className="block text-xs font-semibold text-slate-700">
                Text Alignment
                <div className="grid grid-cols-3 gap-1 mt-1">
                  {["left", "center", "right"].map((align) => (
                    <button
                      key={align}
                      type="button"
                      onClick={() => onUpdateBlock(selectedBlock!.id, { align } as any)}
                      className={`py-1 text-xs rounded border capitalize transition-all cursor-pointer ${
                        (selectedBlock as any).align === align
                          ? "bg-red-50 border-red-500 text-red-600 font-bold"
                          : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      {align}
                    </button>
                  ))}
                </div>
              </label>

              <label className="block text-xs font-semibold text-slate-700">
                Font Size (px)
                <Input
                  type="number"
                  className="mt-1 text-xs"
                  value={(selectedBlock as any).fontSize || (selectedBlock as any).valueFontSize || 10}
                  onChange={(e) =>
                    onUpdateBlock(selectedBlock!.id, {
                      fontSize: Number(e.target.value),
                      valueFontSize: Number(e.target.value),
                    } as any)
                  }
                />
              </label>

              <label className="block text-xs font-semibold text-slate-700">
                Font Weight
                <Select
                  className="mt-1 text-xs"
                  value={(selectedBlock as any).fontWeight || "600"}
                  onChange={(e) => onUpdateBlock(selectedBlock!.id, { fontWeight: e.target.value } as any)}
                >
                  <option value="400">Regular (400)</option>
                  <option value="600">SemiBold (600)</option>
                  <option value="700">Bold (700)</option>
                  <option value="800">ExtraBold (800)</option>
                </Select>
              </label>
            </div>
          )}
        </div>
      )}

      {/* Tab 3: DOM Tree Structure */}
      {activeTab === "structure" && (
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-2">
            Document DOM Tree
          </p>
          <div className="space-y-1">
            {tree.sections.map((sec) => (
              <div key={sec.id} className="border border-slate-200 rounded overflow-hidden">
                <div className="bg-slate-100 p-1.5 text-[11px] font-bold text-slate-800 flex items-center justify-between">
                  <span>{sec.name}</span>
                  <span className="text-[10px] text-slate-600 font-normal">{sec.containers.length} cols</span>
                </div>
                <div className="p-1 space-y-1 bg-white">
                  {sec.containers.map((cont) => (
                    <div key={cont.id} className="pl-2 border-l-2 border-slate-200 space-y-1">
                      {cont.blocks.map((b) => (
                        <button
                          key={b.id}
                          type="button"
                          onClick={() => onSelectBlock(b.id)}
                          className={`w-full text-left p-1 rounded text-[11px] transition-all cursor-pointer flex items-center justify-between ${
                            b.id === selectedBlockId
                              ? "bg-red-50 text-red-700 font-bold border border-red-200"
                              : "text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          <span className="truncate">{b.id}</span>
                          <span className="text-[10px] opacity-70">[{b.type}]</span>
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}
