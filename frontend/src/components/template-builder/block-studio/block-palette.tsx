"use client";

import {
  BracketsCurly,
  FileText,
  FolderSimplePlus,
  GridFour,
  Image,
  ListDashes,
  Plus,
  Receipt,
  Rows,
  Sparkle,
  SquareSplitHorizontal,
  TextT,
} from "@phosphor-icons/react";
import type { BlockType } from "@/lib/template-block-engine";

interface BlockPaletteProps {
  onAddSection: (type: "header" | "body" | "benefits" | "footer") => void;
  onAddBlock: (type: BlockType) => void;
}

export function BlockPalette({ onAddSection, onAddBlock }: BlockPaletteProps) {
  const basicBlocks: Array<{ type: BlockType; label: string; desc: string; icon: any }> = [
    {
      type: "variable_with_title",
      label: "Variable with Title",
      desc: "e.g. Insurer : QBE, Ref : RL260000308",
      icon: BracketsCurly,
    },
    {
      type: "variable",
      label: "Standalone Variable",
      desc: "Pure dynamic value (e.g. AmAssurance)",
      icon: Sparkle,
    },
    {
      type: "text",
      label: "Static Text",
      desc: "Fixed label or title text block",
      icon: TextT,
    },
    {
      type: "image",
      label: "Image / Asset Slot",
      desc: "Logo, QR, or bank payment graphic",
      icon: Image,
    },
    {
      type: "specs_table",
      label: "Specs Table",
      desc: "Vehicle & coverage key-value rows",
      icon: ListDashes,
    },
    {
      type: "premium_block",
      label: "Premium Breakdown",
      desc: "Dynamic extras, roadtax & total",
      icon: Receipt,
    },
    {
      type: "benefits_grid",
      label: "Benefits Grid",
      desc: "Dynamic insurer cards with auto-density",
      icon: GridFour,
    },
  ];

  return (
    <aside className="w-64 border-r border-[var(--rl-border)] bg-white flex flex-col h-full select-none">
      <div className="p-3 border-b border-[var(--rl-border)] flex items-center justify-between bg-slate-50/50">
        <span className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
          <FolderSimplePlus size={15} weight="bold" className="text-red-600" />
          Blocks Palette
        </span>
        <span className="text-[10px] font-semibold text-slate-600 bg-slate-200/60 px-1.5 py-0.5 rounded">
          Container DOM
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {/* Sections Section */}
        <div>
          <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider block mb-2">
            Add Section Container
          </span>
          <div className="grid grid-cols-2 gap-1.5">
            <button
              type="button"
              onClick={() => onAddSection("header")}
              className="flex items-center gap-1.5 p-2 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-slate-300 text-left transition-all cursor-pointer group"
            >
              <Rows size={14} className="text-slate-600 group-hover:text-red-600" />
              <span className="text-[11px] font-semibold text-slate-700">Header</span>
            </button>
            <button
              type="button"
              onClick={() => onAddSection("body")}
              className="flex items-center gap-1.5 p-2 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-slate-300 text-left transition-all cursor-pointer group"
            >
              <SquareSplitHorizontal size={14} className="text-slate-600 group-hover:text-red-600" />
              <span className="text-[11px] font-semibold text-slate-700">Body (2-Col)</span>
            </button>
            <button
              type="button"
              onClick={() => onAddSection("benefits")}
              className="flex items-center gap-1.5 p-2 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-slate-300 text-left transition-all cursor-pointer group"
            >
              <GridFour size={14} className="text-slate-600 group-hover:text-red-600" />
              <span className="text-[11px] font-semibold text-slate-700">Benefits</span>
            </button>
            <button
              type="button"
              onClick={() => onAddSection("footer")}
              className="flex items-center gap-1.5 p-2 rounded border border-slate-200 bg-slate-50 hover:bg-slate-100 hover:border-slate-300 text-left transition-all cursor-pointer group"
            >
              <FileText size={14} className="text-slate-600 group-hover:text-red-600" />
              <span className="text-[11px] font-semibold text-slate-700">Footer</span>
            </button>
          </div>
        </div>

        {/* Content Elements */}
        <div>
          <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider block mb-2">
            Add Element Block
          </span>
          <div className="space-y-1.5">
            {basicBlocks.map((blk) => {
              const Icon = blk.icon;
              return (
                <button
                  key={blk.type}
                  type="button"
                  onClick={() => onAddBlock(blk.type)}
                  className="w-full flex items-start gap-2.5 p-2 rounded border border-slate-200/90 bg-white hover:bg-red-50/50 hover:border-red-200 text-left transition-all cursor-pointer group shadow-xs"
                >
                  <div className="p-1.5 rounded bg-slate-100 group-hover:bg-red-100 text-slate-600 group-hover:text-red-600 shrink-0">
                    <Icon size={16} weight="bold" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-[12px] font-semibold text-slate-800 leading-tight">
                      {blk.label}
                    </p>
                    <p className="text-[10px] text-slate-600 leading-tight mt-0.5 truncate">
                      {blk.desc}
                    </p>
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
