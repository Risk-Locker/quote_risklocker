"use client";

import {
  BracketsCurly,
  Columns,
  CreditCard,
  FileText,
  GridFour,
  Image,
  ListDashes,
  Plus,
  Rows,
  Sparkle,
  SquareSplitHorizontal,
  TextT,
} from "@phosphor-icons/react";
import type { BlockType } from "./types";

interface PalettePanelProps {
  onAddSection: () => void;
  onAddContainer: (preset: "1-col" | "2-col-equal" | "2-col-wide-narrow" | "3-col") => void;
  onAddElement: (type: BlockType) => void;
  selectedContainerId: string | null;
}

export function PalettePanel({
  onAddSection,
  onAddContainer,
  onAddElement,
  selectedContainerId,
}: PalettePanelProps) {
  const containerPresets: Array<{
    id: "1-col" | "2-col-equal" | "2-col-wide-narrow" | "3-col";
    label: string;
    desc: string;
    icon: any;
  }> = [
    {
      id: "1-col",
      label: "Full Width Container",
      desc: "Single 100% column div",
      icon: Rows,
    },
    {
      id: "2-col-equal",
      label: "2 Columns (50% / 50%)",
      desc: "Side-by-side equal split",
      icon: SquareSplitHorizontal,
    },
    {
      id: "2-col-wide-narrow",
      label: "2 Columns (68% / 32%)",
      desc: "Specs table + Bank image split",
      icon: Columns,
    },
    {
      id: "3-col",
      label: "3 Columns (Equal)",
      desc: "3 equal columns row",
      icon: Columns,
    },
  ];

  const elementTypes: Array<{
    type: BlockType;
    label: string;
    desc: string;
    icon: any;
  }> = [
    {
      type: "variable_with_title",
      label: "Variable with Title",
      desc: "Title + Value (e.g. Insurer: QBE)",
      icon: BracketsCurly,
    },
    {
      type: "variable",
      label: "Standalone Variable",
      desc: "Dynamic value only",
      icon: Sparkle,
    },
    {
      type: "text",
      label: "Static Text",
      desc: "Fixed label or title",
      icon: TextT,
    },
    {
      type: "image",
      label: "Image / Logo / QR",
      desc: "1-click upload or company logo",
      icon: Image,
    },
    {
      type: "specs_table",
      label: "Vehicle Specs Table",
      desc: "Car specs & policy parameters",
      icon: ListDashes,
    },
    {
      type: "premium_block",
      label: "Premium Breakdown",
      desc: "Premium, Roadtax & Total",
      icon: CreditCard,
    },
    {
      type: "benefits_grid",
      label: "Benefits Section",
      desc: "Masonry Flow benefit cards",
      icon: GridFour,
    },
  ];

  return (
    <aside className="w-[240px] shrink-0 border-r border-slate-200 bg-white flex flex-col h-full overflow-hidden select-none">
      {/* Panel Header */}
      <div className="p-3 border-b border-slate-200 bg-slate-50/70 shrink-0">
        <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
          <Columns size={15} weight="bold" className="text-blue-600" />
          Elements & Containers
        </h2>
        <p className="text-[10px] text-slate-400 mt-0.5">Click any container or element to insert</p>
      </div>

      <div className="flex-1 overflow-y-auto p-2.5 space-y-4">
        {/* Section Action */}
        <div>
          <button
            type="button"
            onClick={onAddSection}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs shadow-xs transition-colors"
          >
            <Plus size={14} weight="bold" />
            + Add New Section
          </button>
        </div>

        {/* Containers Group (Container Elements) */}
        <div>
          <div className="text-[10.5px] font-bold uppercase tracking-wide text-slate-500 mb-1.5 px-1 flex items-center justify-between">
            <span>Container Elements (Divs)</span>
            <span className="text-[9px] text-slate-400 font-normal">Box Model</span>
          </div>
          <div className="space-y-1">
            {containerPresets.map((preset) => {
              const Icon = preset.icon;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => onAddContainer(preset.id)}
                  className="w-full flex items-start gap-2.5 p-2 rounded-md border border-slate-200 bg-white hover:bg-blue-50/50 hover:border-blue-300 transition-all text-left group"
                >
                  <div className="w-6 h-6 rounded bg-slate-100 group-hover:bg-blue-100 flex items-center justify-center text-slate-600 group-hover:text-blue-600 shrink-0 mt-0.5">
                    <Icon size={14} weight="bold" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold text-slate-800 group-hover:text-blue-700">
                      {preset.label}
                    </div>
                    <div className="text-[10px] text-slate-400 leading-tight">
                      {preset.desc}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Elements Group */}
        <div>
          <div className="text-[10.5px] font-bold uppercase tracking-wide text-slate-500 mb-1.5 px-1 flex items-center justify-between">
            <span>Elements</span>
            {selectedContainerId ? (
              <span className="text-[9px] text-emerald-600 font-semibold">Active target</span>
            ) : (
              <span className="text-[9px] text-slate-400">Inserts to last</span>
            )}
          </div>
          <div className="space-y-1">
            {elementTypes.map((elem) => {
              const Icon = elem.icon;
              return (
                <button
                  key={elem.type}
                  type="button"
                  onClick={() => onAddElement(elem.type)}
                  className="w-full flex items-start gap-2.5 p-2 rounded-md border border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300 transition-all text-left group"
                >
                  <div className="w-6 h-6 rounded bg-slate-100 group-hover:bg-slate-200 flex items-center justify-center text-slate-600 shrink-0 mt-0.5">
                    <Icon size={14} weight="bold" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-semibold text-slate-800 group-hover:text-slate-900">
                      {elem.label}
                    </div>
                    <div className="text-[10px] text-slate-400 leading-tight">
                      {elem.desc}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </aside>
  );
}
