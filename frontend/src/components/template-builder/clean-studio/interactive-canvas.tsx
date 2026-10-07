"use client";

import {
  AlignLeft,
  AlignCenterHorizontal,
  AlignRight,
  ArrowDown,
  ArrowUp,
  BracketsCurly,
  CreditCard,
  GridFour,
  Image,
  ListDashes,
  Plus,
  Sparkle,
  TextT,
  Trash,
} from "@phosphor-icons/react";
import type {
  BlockTree,
  BlockSection,
  BlockContainer,
  TemplateBlock,
  SelectionTarget,
} from "./types";

interface InteractiveCanvasProps {
  tree: BlockTree;
  selection: SelectionTarget | null;
  onSelect: (target: SelectionTarget | null) => void;
  onUpdateContainerWidth: (containerId: string, deltaPercent: number) => void;
  onUpdateContainerAlign: (containerId: string, align: "start" | "center" | "end" | "between") => void;
  onDeleteBlock: (blockId: string) => void;
  onDeleteContainer: (containerId: string) => void;
  onDeleteSection: (sectionId: string) => void;
  onAddElementToContainer: (containerId: string) => void;
}

export function InteractiveCanvas({
  tree,
  selection,
  onSelect,
  onUpdateContainerWidth,
  onUpdateContainerAlign,
  onDeleteBlock,
  onDeleteContainer,
  onDeleteSection,
  onAddElementToContainer,
}: InteractiveCanvasProps) {
  function getWidthPercent(width: string | number | undefined, defaultPercent = 100): number {
    if (!width) return defaultPercent;
    if (typeof width === "number") return Math.min(100, Math.round((width / 794) * 100));
    if (typeof width === "string" && width.endsWith("%")) return parseFloat(width) || defaultPercent;
    return defaultPercent;
  }

  return (
    <div className="flex-1 min-w-[420px] bg-slate-100/80 border-r border-slate-200 flex flex-col h-full overflow-hidden select-none">
      {/* Top Banner */}
      <div className="p-3 border-b border-slate-200 bg-white shrink-0 flex items-center justify-between">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-800 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-blue-600 animate-pulse" />
            Interactive Workspace (Box Model Canvas)
          </h2>
          <p className="text-[10px] text-slate-400 mt-0.5">
            Click any container or element to edit. Adjust container width and alignment below.
          </p>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
          Editable View
        </span>
      </div>

      {/* Scrollable Working Document */}
      <div className="flex-1 overflow-y-auto p-4 flex justify-center">
        <div className="w-full max-w-[760px] bg-white rounded-lg shadow-sm border border-slate-300 p-5 space-y-4">
          {tree.sections.map((section, sIdx) => {
            const isSectionSelected = selection?.type === "section" && selection?.id === section.id;

            return (
              <section
                key={section.id}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect({ type: "section", id: section.id });
                }}
                className={`rounded-lg border-2 p-3 transition-all ${
                  isSectionSelected
                    ? "border-blue-500 bg-blue-50/20 ring-2 ring-blue-200"
                    : "border-slate-300 bg-slate-50/50 hover:border-slate-400"
                }`}
              >
                {/* Section Header Bar */}
                <div className="flex items-center justify-between pb-2 mb-2 border-b border-slate-200">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide bg-slate-200 text-slate-700">
                      Section {sIdx + 1}: {section.name}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">
                      {section.containers.length} container{section.containers.length === 1 ? "" : "s"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSection(section.id);
                      }}
                      className="p-1 rounded text-slate-400 hover:text-red-600 hover:bg-red-50"
                      title="Delete section"
                    >
                      <Trash size={12} />
                    </button>
                  </div>
                </div>

                {/* Section Containers Row / Grid */}
                <div className="flex flex-wrap gap-2.5 items-stretch">
                  {section.containers.map((container, cIdx) => {
                    const isContainerSelected =
                      selection?.type === "container" && selection?.id === container.id;
                    const wPct = getWidthPercent(
                      container.width,
                      section.containers.length === 2 ? (cIdx === 0 ? 68 : 32) : 100
                    );

                    return (
                      <div
                        key={container.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelect({
                            type: "container",
                            id: container.id,
                            sectionId: section.id,
                          });
                        }}
                        style={{
                          width: section.containers.length > 1 ? `calc(${wPct}% - 6px)` : "100%",
                          minWidth: "180px",
                          background: container.background || "#FFFFFF",
                        }}
                        className={`rounded-md border p-2.5 transition-all flex flex-col gap-2 relative ${
                          isContainerSelected
                            ? "border-blue-600 ring-2 ring-blue-300 bg-blue-50/30"
                            : "border-slate-300 hover:border-slate-400 bg-white"
                        }`}
                      >
                        {/* Container Toolbar */}
                        <div className="flex items-center justify-between pb-1.5 border-b border-slate-100 text-[10px]">
                          {/* Width adjuster */}
                          <div className="flex items-center gap-1">
                            <span className="font-bold text-slate-600">Width:</span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onUpdateContainerWidth(container.id, -5);
                              }}
                              className="w-4 h-4 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold flex items-center justify-center text-xs"
                              title="Shrink width by 5%"
                            >
                              -
                            </button>
                            <span className="font-mono font-bold text-blue-700 min-w-8 text-center">
                              {wPct}%
                            </span>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onUpdateContainerWidth(container.id, 5);
                              }}
                              className="w-4 h-4 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold flex items-center justify-center text-xs"
                              title="Expand width by 5%"
                            >
                              +
                            </button>
                          </div>

                          {/* Alignment Buttons */}
                          <div className="flex items-center gap-0.5 bg-slate-100 rounded p-0.5">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onUpdateContainerAlign(container.id, "start");
                              }}
                              className={`p-1 rounded ${
                                container.justifyContent === "start" || !container.justifyContent
                                  ? "bg-white text-blue-700 shadow-xs"
                                  : "text-slate-400 hover:text-slate-700"
                              }`}
                              title="Align content left"
                            >
                              <AlignLeft size={11} weight="bold" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onUpdateContainerAlign(container.id, "center");
                              }}
                              className={`p-1 rounded ${
                                container.justifyContent === "center"
                                  ? "bg-white text-blue-700 shadow-xs"
                                  : "text-slate-400 hover:text-slate-700"
                              }`}
                              title="Align content center"
                            >
                              <AlignCenterHorizontal size={11} weight="bold" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onUpdateContainerAlign(container.id, "end");
                              }}
                              className={`p-1 rounded ${
                                container.justifyContent === "end"
                                  ? "bg-white text-blue-700 shadow-xs"
                                  : "text-slate-400 hover:text-slate-700"
                              }`}
                              title="Align content right"
                            >
                              <AlignRight size={11} weight="bold" />
                            </button>
                          </div>

                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onDeleteContainer(container.id);
                            }}
                            className="p-1 rounded text-slate-400 hover:text-red-600"
                            title="Delete container"
                          >
                            <Trash size={11} />
                          </button>
                        </div>

                        {/* Blocks in Container */}
                        <div
                          className={`flex flex-col gap-1.5 min-h-[44px] ${
                            container.direction === "row" ? "!flex-row flex-wrap" : ""
                          }`}
                        >
                          {container.blocks.map((block) => {
                            const isBlockSelected =
                              selection?.type === "block" && selection?.id === block.id;

                            return (
                              <div
                                key={block.id}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onSelect({
                                    type: "block",
                                    id: block.id,
                                    containerId: container.id,
                                    sectionId: section.id,
                                  });
                                }}
                                className={`p-2 rounded border transition-all text-xs flex items-center justify-between cursor-pointer ${
                                  isBlockSelected
                                    ? "border-blue-600 bg-blue-50 ring-2 ring-blue-300"
                                    : "border-slate-200 bg-white hover:border-slate-300 shadow-xs"
                                }`}
                              >
                                <div className="flex items-center gap-1.5 min-w-0 pr-1">
                                  {block.type === "image" && (
                                    <Image size={13} className="text-purple-600 shrink-0" />
                                  )}
                                  {block.type === "variable" && (
                                    <Sparkle size={13} className="text-amber-600 shrink-0" />
                                  )}
                                  {block.type === "variable_with_title" && (
                                    <BracketsCurly size={13} className="text-blue-600 shrink-0" />
                                  )}
                                  {block.type === "text" && (
                                    <TextT size={13} className="text-slate-600 shrink-0" />
                                  )}
                                  {block.type === "specs_table" && (
                                    <ListDashes size={13} className="text-emerald-600 shrink-0" />
                                  )}
                                  {block.type === "premium_block" && (
                                    <CreditCard size={13} className="text-rose-600 shrink-0" />
                                  )}
                                  {block.type === "benefits_grid" && (
                                    <GridFour size={13} className="text-cyan-600 shrink-0" />
                                  )}

                                  <span className="font-semibold text-slate-800 capitalize truncate">
                                    {block.type.replace(/_/g, " ")}
                                  </span>

                                  {"title" in block && (block as any).title && (
                                    <span className="text-[10px] text-slate-400 truncate">
                                      ({(block as any).title})
                                    </span>
                                  )}

                                  {"variableId" in block && (
                                    <span className="font-mono text-[9.5px] px-1 py-0.2 rounded bg-blue-50 text-blue-700 truncate">
                                      {(block as any).variableId}
                                    </span>
                                  )}
                                </div>

                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onDeleteBlock(block.id);
                                  }}
                                  className="text-slate-400 hover:text-red-600 p-0.5 rounded shrink-0 ml-1"
                                  title="Delete element"
                                >
                                  <Trash size={11} />
                                </button>
                              </div>
                            );
                          })}

                          {container.blocks.length === 0 && (
                            <div className="text-[10px] text-slate-400 italic text-center py-2 border border-dashed border-slate-200 rounded w-full">
                              Empty container. Click + Add Element below.
                            </div>
                          )}
                        </div>

                        {/* Add Element to container button */}
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onAddElementToContainer(container.id);
                          }}
                          className="w-full py-1 text-[10px] font-semibold text-blue-600 hover:text-blue-700 hover:bg-blue-50/60 rounded border border-dashed border-blue-200 flex items-center justify-center gap-1 transition-colors"
                        >
                          <Plus size={11} weight="bold" />
                          + Add Element Inside Container
                        </button>
                      </div>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      </div>
    </div>
  );
}
