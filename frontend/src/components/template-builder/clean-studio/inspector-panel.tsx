"use client";

import { useMemo, useRef, useState } from "react";
import {
  AlignLeft,
  AlignCenterHorizontal,
  AlignRight,
  ArrowsHorizontal,
  BracketsCurly,
  CaretDown,
  CaretRight,
  Columns,
  CreditCard,
  FolderSimple,
  GridFour,
  Image,
  ListDashes,
  Plus,
  Rows,
  Sparkle,
  SplitHorizontal,
  TextT,
  Trash,
  UploadSimple,
} from "@phosphor-icons/react";
import type {
  BlockTree,
  BlockSection,
  BlockContainer,
  TemplateBlock,
  SelectionTarget,
  ImageBlock,
  TextBlock,
  VariableBlock,
  VariableWithTitleBlock,
  SpecsTableBlock,
} from "./types";
import { api } from "@/lib/api";

interface InspectorPanelProps {
  tree: BlockTree;
  selection: SelectionTarget | null;
  onSelect: (target: SelectionTarget | null) => void;
  onUpdateContainer: (containerId: string, updates: Partial<BlockContainer>) => void;
  onUpdateBlock: (blockId: string, updates: Partial<TemplateBlock>) => void;
  onUpdateSection: (sectionId: string, updates: Partial<BlockSection>) => void;
  onAddContainerToSection: (sectionId: string) => void;
  onAddSubContainerToContainer?: (containerId: string) => void;
  onAddElementToContainer: (containerId: string) => void;
  onDeleteBlock: (blockId: string) => void;
  onDeleteContainer: (containerId: string) => void;
  onDeleteSection?: (sectionId: string) => void;
}

const AVAILABLE_VARIABLES = [
  { id: "customer_name", label: "Customer Name" },
  { id: "vehicle_no", label: "Vehicle Number / Plate" },
  { id: "insurance_company", label: "Insurance Company (Insurer)" },
  { id: "coverage_type", label: "Coverage Type (Comprehensive)" },
  { id: "cover_period", label: "Cover Period" },
  { id: "car_model", label: "Car Model" },
  { id: "engine_cc", label: "Engine Capacity / cc" },
  { id: "ncd_percent", label: "NCD %" },
  { id: "valuation_type", label: "Valuation Type" },
  { id: "authorized_driver", label: "Authorised Driver (All / Named)" },
  { id: "excess_amount", label: "Policy Excess" },
  { id: "coverage_amount", label: "Vehicle Sum Insured" },
  { id: "premium", label: "Insurance Premium" },
  { id: "roadtax", label: "Road Tax & Runner Fee" },
  { id: "total_amount", label: "Total Payable" },
  { id: "valid_until", label: "Quotation Validity" },
  { id: "quotation_reference", label: "Quotation Reference" },
];

const DYNAMIC_IMAGE_VARIABLES = [
  { id: "insurance_company_logo", label: "Dynamic Insurer Logo (Sompo, QBE, Etiqa...)" },
  { id: "bank_qr", label: "Dynamic DuitNow Bank QR" },
  { id: "risklocker_logo", label: "RiskLocker Official Logo" },
];

type SelectedEntity =
  | { type: "section"; item: BlockSection }
  | { type: "container"; item: BlockContainer; section?: BlockSection; parentContainer?: BlockContainer }
  | { type: "block"; item: TemplateBlock; container: BlockContainer; section?: BlockSection };

// Helper to find a container recursively in nested trees
function findContainerRecursively(
  containers: BlockContainer[],
  targetId: string,
  parent?: BlockContainer
): { container: BlockContainer; parent?: BlockContainer } | null {
  for (const c of containers) {
    if (c.id === targetId) return { container: c, parent };
    if (c.containers?.length) {
      const match = findContainerRecursively(c.containers, targetId, c);
      if (match) return match;
    }
  }
  return null;
}

// Helper to find a block recursively in containers
function findBlockRecursively(
  containers: BlockContainer[],
  targetId: string
): { block: TemplateBlock; container: BlockContainer } | null {
  for (const c of containers) {
    const b = c.blocks?.find((blk) => blk.id === targetId);
    if (b) return { block: b, container: c };
    if (c.containers?.length) {
      const match = findBlockRecursively(c.containers, targetId);
      if (match) return match;
    }
  }
  return null;
}

export function InspectorPanel({
  tree,
  selection,
  onSelect,
  onUpdateContainer,
  onUpdateBlock,
  onUpdateSection,
  onAddContainerToSection,
  onAddSubContainerToContainer,
  onAddElementToContainer,
  onDeleteBlock,
  onDeleteContainer,
  onDeleteSection,
}: InspectorPanelProps) {
  const [viewMode, setViewMode] = useState<"split" | "structure" | "properties">("split");
  const [collapsedNodes, setCollapsedNodes] = useState<Record<string, boolean>>({});
  const [uploadingImage, setUploadingImage] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function toggleCollapse(id: string) {
    setCollapsedNodes((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  // Find currently selected entity with strict typing
  const selectedEntity = useMemo((): SelectedEntity | null => {
    if (!selection) return null;
    if (selection.type === "section") {
      const sec = tree.sections.find((s) => s.id === selection.id);
      if (sec) return { type: "section", item: sec };
    }
    if (selection.type === "container") {
      for (const sec of tree.sections) {
        const match = findContainerRecursively(sec.containers, selection.id);
        if (match) {
          return {
            type: "container",
            item: match.container,
            section: sec,
            parentContainer: match.parent,
          };
        }
      }
    }
    if (selection.type === "block") {
      for (const sec of tree.sections) {
        const match = findBlockRecursively(sec.containers, selection.id);
        if (match) {
          return {
            type: "block",
            item: match.block,
            container: match.container,
            section: sec,
          };
        }
      }
    }
    return null;
  }, [selection, tree]);

  // Direct 1-click image upload handler
  async function handleDirectImageUpload(e: React.ChangeEvent<HTMLInputElement>, blockId: string) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingImage(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("label", file.name.replace(/\.[^/.]+$/, ""));
      formData.append("kind", "company_logo");
      formData.append("category", "Template Assets");

      const res = await api<{ asset: { id: string; url: string } }>("/business/assets", {
        method: "POST",
        body: formData,
      });

      if (res.asset?.url) {
        onUpdateBlock(blockId, {
          url: res.asset.url,
          assetSlot: res.asset.id,
        } as any);
      }
    } catch (err) {
      console.error("Direct image upload failed:", err);
    } finally {
      setUploadingImage(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  // Recursive renderer for container nodes in the hierarchy tree
  function renderContainerNode(
    container: BlockContainer,
    depth: number,
    sectionId: string,
    parentContainerId?: string
  ) {
    const isCollapsed = collapsedNodes[container.id];
    const isSelected = selection?.type === "container" && selection?.id === container.id;

    return (
      <div key={container.id} className="space-y-0.5">
        {/* Container Node Row */}
        <div
          onClick={(e) => {
            e.stopPropagation();
            onSelect({
              type: "container",
              id: container.id,
              sectionId,
              containerId: parentContainerId,
            });
          }}
          className={`group flex items-center justify-between py-1 px-1.5 rounded cursor-pointer transition-colors text-[11px] ${
            isSelected
              ? "bg-blue-100 text-blue-900 font-bold ring-1 ring-blue-400"
              : "hover:bg-slate-100 text-slate-700"
          }`}
          style={{ paddingLeft: `${depth * 10 + 4}px` }}
        >
          <div className="flex items-center gap-1.5 min-w-0 flex-1 truncate">
            {(container.containers?.length || container.blocks?.length) ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  toggleCollapse(container.id);
                }}
                className="text-slate-400 hover:text-slate-700 p-0.5 rounded"
              >
                {isCollapsed ? <CaretRight size={10} weight="bold" /> : <CaretDown size={10} weight="bold" />}
              </button>
            ) : (
              <span className="w-3" />
            )}

            <Columns size={12} className="text-purple-600 shrink-0" weight="bold" />
            <span className="truncate">
              {depth > 0 ? "Sub-Container" : "Container"} ({container.width || "100%"})
            </span>
          </div>

          {/* Quick Action buttons */}
          <div className="flex items-center gap-0.5 opacity-70 group-hover:opacity-100">
            {onAddSubContainerToContainer && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onAddSubContainerToContainer(container.id);
                }}
                className="p-1 rounded text-slate-400 hover:text-purple-700 hover:bg-purple-50"
                title="Add sub-container inside this container"
              >
                <Plus size={10} weight="bold" />
              </button>
            )}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onAddElementToContainer(container.id);
              }}
              className="p-1 rounded text-slate-400 hover:text-blue-700 hover:bg-blue-50"
              title="Add element inside this container"
            >
              <Plus size={10} weight="bold" />
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onDeleteContainer(container.id);
              }}
              className="p-1 rounded text-slate-400 hover:text-red-600 hover:bg-red-50"
              title="Delete container"
            >
              <Trash size={10} />
            </button>
          </div>
        </div>

        {/* Nested Content: Sub-containers & Blocks */}
        {!isCollapsed && (
          <div className="border-l border-indigo-200 ml-3 pl-1 space-y-0.5">
            {/* Render any sub-containers first */}
            {container.containers?.map((sub) =>
              renderContainerNode(sub, depth + 1, sectionId, container.id)
            )}

            {/* Render blocks inside this container */}
            {container.blocks?.map((block) => {
              const isBlockSelected = selection?.type === "block" && selection?.id === block.id;

              return (
                <div
                  key={block.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect({
                      type: "block",
                      id: block.id,
                      containerId: container.id,
                      sectionId,
                    });
                  }}
                  className={`group flex items-center justify-between py-1 px-1.5 rounded cursor-pointer transition-colors text-[11px] ${
                    isBlockSelected
                      ? "bg-blue-100 text-blue-900 font-bold ring-1 ring-blue-400"
                      : "hover:bg-slate-100 text-slate-600"
                  }`}
                  style={{ paddingLeft: `${(depth + 1) * 8}px` }}
                >
                  <div className="flex items-center gap-1.5 min-w-0 flex-1 truncate">
                    {block.type === "image" && <Image size={11} className="text-purple-600 shrink-0" />}
                    {block.type === "text" && <TextT size={11} className="text-slate-600 shrink-0" />}
                    {block.type === "variable" && <Sparkle size={11} className="text-amber-600 shrink-0" />}
                    {block.type === "variable_with_title" && <BracketsCurly size={11} className="text-blue-600 shrink-0" />}
                    {block.type === "specs_table" && <ListDashes size={11} className="text-emerald-600 shrink-0" />}
                    {block.type === "premium_block" && <CreditCard size={11} className="text-rose-600 shrink-0" />}
                    {block.type === "benefits_grid" && <GridFour size={11} className="text-cyan-600 shrink-0" />}

                    <span className="truncate">
                      {"title" in block && (block as any).title
                        ? (block as any).title
                        : "variableId" in block && (block as any).variableId
                        ? `{${(block as any).variableId}}`
                        : block.type.replace(/_/g, " ")}
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteBlock(block.id);
                    }}
                    className="p-1 rounded text-slate-400 hover:text-red-600 opacity-60 group-hover:opacity-100"
                    title="Delete element"
                  >
                    <Trash size={10} />
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>
    );
  }

  // Render the Tree Hierarchy Component
  function renderStructureTree() {
    return (
      <div className="space-y-1">
        <div className="pb-1.5 mb-2 border-b border-slate-200 flex items-center justify-between text-slate-700 font-bold text-[11px]">
          <span>Document Hierarchy</span>
          <span className="text-[9.5px] text-slate-400 font-mono">Nested Tree</span>
        </div>

        {tree.sections.map((section, sIdx) => {
          const isSecCollapsed = collapsedNodes[section.id];
          const isSecSelected = selection?.type === "section" && selection?.id === section.id;

          return (
            <div key={section.id} className="space-y-0.5">
              {/* Section Row */}
              <div
                onClick={() => onSelect({ type: "section", id: section.id })}
                className={`group flex items-center justify-between py-1 px-1.5 rounded cursor-pointer transition-colors text-[11.5px] ${
                  isSecSelected
                    ? "bg-blue-100 text-blue-900 font-bold ring-1 ring-blue-400"
                    : "hover:bg-slate-100 text-slate-800"
                }`}
              >
                <div className="flex items-center gap-1.5 min-w-0 flex-1 truncate">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleCollapse(section.id);
                    }}
                    className="text-slate-400 hover:text-slate-700 p-0.5 rounded"
                  >
                    {isSecCollapsed ? <CaretRight size={10} weight="bold" /> : <CaretDown size={10} weight="bold" />}
                  </button>
                  <FolderSimple size={13} className="text-blue-600 shrink-0" weight="fill" />
                  <span className="truncate font-semibold">
                    {section.name || `Section ${sIdx + 1}`}
                  </span>
                </div>

                <div className="flex items-center gap-1 opacity-70 group-hover:opacity-100">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAddContainerToSection(section.id);
                    }}
                    className="px-1.5 py-0.5 rounded text-[10px] font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 flex items-center gap-0.5"
                    title="Add container inside section"
                  >
                    <Plus size={10} weight="bold" />
                    Container
                  </button>
                  {onDeleteSection && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteSection(section.id);
                      }}
                      className="p-1 rounded text-slate-400 hover:text-red-600"
                      title="Delete section"
                    >
                      <Trash size={10} />
                    </button>
                  )}
                </div>
              </div>

              {/* Containers in Section */}
              {!isSecCollapsed && (
                <div className="border-l-2 border-slate-200 ml-2.5 pl-1.5 space-y-0.5">
                  {section.containers.map((container) =>
                    renderContainerNode(container, 0, section.id)
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  // Render the Properties Inspector for Selected Item
  function renderPropertiesInspector() {
    if (!selectedEntity) {
      return (
        <div className="text-center py-8 px-4 text-slate-400">
          <FolderSimple size={28} className="mx-auto text-slate-300 mb-2" />
          <p className="font-semibold text-slate-600 text-xs">No element selected</p>
          <p className="text-[10.5px] mt-1">
            Click any container or element in the hierarchy tree or canvas to configure its settings.
          </p>
        </div>
      );
    }

    if (selectedEntity.type === "section") {
      const sec = selectedEntity.item;
      return (
        <div className="space-y-3">
          <div className="flex items-center justify-between pb-1.5 border-b border-slate-200">
            <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
              <FolderSimple size={14} className="text-blue-600" weight="fill" />
              Section Settings
            </span>
            <span className="text-[10px] font-mono text-slate-400">ID: {sec.id}</span>
          </div>

          <div>
            <label className="font-semibold text-slate-700 block mb-1 text-[11px]">Section Name:</label>
            <input
              type="text"
              value={sec.name}
              onChange={(e) => onUpdateSection(sec.id, { name: e.target.value })}
              className="w-full bg-white border border-slate-300 rounded p-1.5 text-xs focus:ring-1 focus:ring-blue-500"
            />
          </div>

          <button
            type="button"
            onClick={() => onAddContainerToSection(sec.id)}
            className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold"
          >
            <Plus size={12} weight="bold" />
            Add Container Inside Section
          </button>
        </div>
      );
    }

    if (selectedEntity.type === "container") {
      const cnt = selectedEntity.item;
      return (
        <div className="space-y-3.5">
          <div className="flex items-center justify-between pb-1.5 border-b border-slate-200">
            <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5">
              <Columns size={14} className="text-blue-600" weight="bold" />
              Container Box Model
            </span>
            <span className="text-[10px] font-mono text-slate-400">ID: {cnt.id.slice(-6)}</span>
          </div>

          {/* Width Controls */}
          <div>
            <div className="flex justify-between items-center mb-1">
              <span className="font-semibold text-slate-700 text-[11px]">Container Width:</span>
              <span className="font-mono font-bold text-blue-700 text-xs">
                {cnt.width || "100%"}
              </span>
            </div>
            <div className="grid grid-cols-5 gap-1 text-[10px]">
              {["25%", "33%", "50%", "68%", "100%"].map((pct) => (
                <button
                  key={pct}
                  type="button"
                  onClick={() => onUpdateContainer(cnt.id, { width: pct })}
                  className={`py-1 rounded border font-semibold ${
                    cnt.width === pct
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  {pct}
                </button>
              ))}
            </div>
          </div>

          {/* Content Alignment */}
          <div>
            <span className="font-semibold text-slate-700 block mb-1 text-[11px]">
              Content Alignment:
            </span>
            <div className="grid grid-cols-4 gap-1">
              {[
                { id: "start", label: "Left", icon: AlignLeft },
                { id: "center", label: "Center", icon: AlignCenterHorizontal },
                { id: "end", label: "Right", icon: AlignRight },
                { id: "between", label: "Split", icon: ArrowsHorizontal },
              ].map((align) => {
                const Icon = align.icon;
                const isCur =
                  cnt.justifyContent === align.id ||
                  (!cnt.justifyContent && align.id === "start");
                return (
                  <button
                    key={align.id}
                    type="button"
                    onClick={() =>
                      onUpdateContainer(cnt.id, { justifyContent: align.id as any })
                    }
                    className={`flex items-center justify-center gap-1 py-1 rounded border text-[10px] font-semibold ${
                      isCur
                        ? "bg-blue-600 text-white border-blue-600"
                        : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                    }`}
                  >
                    <Icon size={11} weight="bold" />
                    {align.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Direction */}
          <div>
            <span className="font-semibold text-slate-700 block mb-1 text-[11px]">Direction:</span>
            <div className="grid grid-cols-2 gap-1 text-[10.5px]">
              <button
                type="button"
                onClick={() => onUpdateContainer(cnt.id, { direction: "row" })}
                className={`py-1 rounded border font-semibold flex items-center justify-center gap-1 ${
                  cnt.direction === "row"
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-slate-600 border-slate-200"
                }`}
              >
                <Columns size={12} />
                Row (Horizontal)
              </button>
              <button
                type="button"
                onClick={() => onUpdateContainer(cnt.id, { direction: "column" })}
                className={`py-1 rounded border font-semibold flex items-center justify-center gap-1 ${
                  cnt.direction === "column" || !cnt.direction
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-slate-600 border-slate-200"
                }`}
              >
                <Rows size={12} />
                Column (Vertical)
              </button>
            </div>
          </div>

          {/* Colors & Styling */}
          <div className="space-y-2 pt-2 border-t border-slate-200">
            <span className="font-semibold text-slate-700 block text-[11px]">Colors & Borders:</span>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-600">Background:</span>
              <input
                type="color"
                value={cnt.background || "#FFFFFF"}
                onChange={(e) => onUpdateContainer(cnt.id, { background: e.target.value })}
                className="w-6 h-6 rounded border border-slate-300 cursor-pointer p-0"
              />
            </div>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-slate-600">Border Color:</span>
              <input
                type="color"
                value={cnt.borderColor || "#E2E8F0"}
                onChange={(e) => onUpdateContainer(cnt.id, { borderColor: e.target.value })}
                className="w-6 h-6 rounded border border-slate-300 cursor-pointer p-0"
              />
            </div>
          </div>
        </div>
      );
    }

    if (selectedEntity.type === "block") {
      const blk = selectedEntity.item;
      return (
        <div className="space-y-3.5">
          <div className="flex items-center justify-between pb-1.5 border-b border-slate-200">
            <span className="font-bold text-slate-800 text-xs flex items-center gap-1.5 capitalize">
              <Sparkle size={14} className="text-blue-600" />
              {blk.type.replace(/_/g, " ")}
            </span>
            <span className="text-[10px] font-mono text-slate-400">ID: {blk.id.slice(-6)}</span>
          </div>

          {/* VARIABLE WITH TITLE */}
          {blk.type === "variable_with_title" && (
            <div className="space-y-2 text-[11px]">
              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">Title Label:</label>
                <input
                  type="text"
                  value={blk.title || ""}
                  onChange={(e) => onUpdateBlock(blk.id, { title: e.target.value })}
                  className="w-full bg-white border border-slate-300 rounded p-1.5 text-xs"
                />
              </div>

              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">Quotation Variable:</label>
                <select
                  value={blk.variableId || ""}
                  onChange={(e) => onUpdateBlock(blk.id, { variableId: e.target.value })}
                  className="w-full bg-white border border-slate-300 rounded p-1.5 text-xs font-mono"
                >
                  {AVAILABLE_VARIABLES.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label} ({v.id})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2 pt-1">
                <div>
                  <span className="text-slate-600 block mb-0.5">Title Color:</span>
                  <input
                    type="color"
                    value={blk.titleColor || "#0F172A"}
                    onChange={(e) => onUpdateBlock(blk.id, { titleColor: e.target.value })}
                    className="w-full h-7 rounded border border-slate-300 p-0 cursor-pointer"
                  />
                </div>
                <div>
                  <span className="text-slate-600 block mb-0.5">Value Color:</span>
                  <input
                    type="color"
                    value={blk.valueColor || "#ED1C24"}
                    onChange={(e) => onUpdateBlock(blk.id, { valueColor: e.target.value })}
                    className="w-full h-7 rounded border border-slate-300 p-0 cursor-pointer"
                  />
                </div>
              </div>
            </div>
          )}

          {/* STANDALONE VARIABLE */}
          {blk.type === "variable" && (
            <div className="space-y-2 text-[11px]">
              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">Quotation Variable:</label>
                <select
                  value={blk.variableId || ""}
                  onChange={(e) => onUpdateBlock(blk.id, { variableId: e.target.value })}
                  className="w-full bg-white border border-slate-300 rounded p-1.5 text-xs font-mono"
                >
                  {AVAILABLE_VARIABLES.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label} ({v.id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">Prefix / Suffix:</label>
                <div className="grid grid-cols-2 gap-1">
                  <input
                    type="text"
                    placeholder="Prefix"
                    value={blk.prefix || ""}
                    onChange={(e) => onUpdateBlock(blk.id, { prefix: e.target.value })}
                    className="w-full bg-white border border-slate-300 rounded p-1 text-xs"
                  />
                  <input
                    type="text"
                    placeholder="Suffix"
                    value={blk.suffix || ""}
                    onChange={(e) => onUpdateBlock(blk.id, { suffix: e.target.value })}
                    className="w-full bg-white border border-slate-300 rounded p-1 text-xs"
                  />
                </div>
              </div>
            </div>
          )}

          {/* STATIC TEXT */}
          {blk.type === "text" && (
            <div className="space-y-2 text-[11px]">
              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">Text Content:</label>
                <textarea
                  rows={2}
                  value={blk.text || ""}
                  onChange={(e) => onUpdateBlock(blk.id, { text: e.target.value })}
                  className="w-full bg-white border border-slate-300 rounded p-1.5 text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-slate-600 block mb-0.5">Font Size (px):</span>
                  <input
                    type="number"
                    value={blk.fontSize || 12}
                    onChange={(e) => onUpdateBlock(blk.id, { fontSize: parseFloat(e.target.value) || 12 })}
                    className="w-full bg-white border border-slate-300 rounded p-1 text-xs"
                  />
                </div>
                <div>
                  <span className="text-slate-600 block mb-0.5">Color:</span>
                  <input
                    type="color"
                    value={blk.color || "#0F172A"}
                    onChange={(e) => onUpdateBlock(blk.id, { color: e.target.value })}
                    className="w-full h-7 rounded border border-slate-300 p-0 cursor-pointer"
                  />
                </div>
              </div>
            </div>
          )}

          {/* IMAGE / LOGO / QR */}
          {blk.type === "image" && (
            <div className="space-y-3 text-[11px]">
              {/* Direct 1-Click Upload */}
              <div className="p-2.5 rounded-lg border-2 border-dashed border-blue-200 bg-blue-50/50">
                <span className="font-semibold text-blue-900 block mb-1">
                  1-Click Direct File Upload:
                </span>
                <input
                  type="file"
                  accept="image/*"
                  ref={fileInputRef}
                  onChange={(e) => handleDirectImageUpload(e, blk.id)}
                  className="hidden"
                  id={`upload_${blk.id}`}
                />
                <label
                  htmlFor={`upload_${blk.id}`}
                  className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs cursor-pointer shadow-xs transition-colors"
                >
                  <UploadSimple size={14} weight="bold" />
                  {uploadingImage ? "Uploading..." : "Choose & Upload File"}
                </label>
                {blk.url && (
                  <div className="mt-2 text-center">
                    <img
                      src={blk.url}
                      alt="Uploaded Asset"
                      className="max-h-16 max-w-full mx-auto object-contain rounded border border-slate-200 bg-white p-1"
                    />
                  </div>
                )}
              </div>

              {/* Dynamic Image Binding */}
              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">
                  Or Dynamic Image Slot:
                </label>
                <select
                  value={blk.assetSlot || ""}
                  onChange={(e) => onUpdateBlock(blk.id, { assetSlot: e.target.value } as any)}
                  className="w-full bg-white border border-slate-300 rounded p-1.5 text-xs"
                >
                  <option value="">-- Fixed File Uploaded --</option>
                  {DYNAMIC_IMAGE_VARIABLES.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Dimensions */}
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-slate-600 block mb-0.5">Width (px):</span>
                  <input
                    type="number"
                    value={blk.width || 100}
                    onChange={(e) => onUpdateBlock(blk.id, { width: parseInt(e.target.value) || 100 } as any)}
                    className="w-full bg-white border border-slate-300 rounded p-1 text-xs"
                  />
                </div>
                <div>
                  <span className="text-slate-600 block mb-0.5">Height (px):</span>
                  <input
                    type="number"
                    value={blk.height || 30}
                    onChange={(e) => onUpdateBlock(blk.id, { height: parseInt(e.target.value) || 30 } as any)}
                    className="w-full bg-white border border-slate-300 rounded p-1 text-xs"
                  />
                </div>
              </div>
            </div>
          )}

          {/* SPECS TABLE */}
          {blk.type === "specs_table" && (
            <div className="space-y-2 text-[11px]">
              <span className="font-semibold text-slate-700 block">Car Specs Table Rows:</span>
              <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
                {blk.rows.map((row, rIdx) => (
                  <div key={row.id} className="flex items-center gap-1 bg-slate-50 p-1 rounded border border-slate-200">
                    <input
                      type="text"
                      value={row.label}
                      onChange={(e) => {
                        const updated = [...blk.rows];
                        updated[rIdx] = { ...row, label: e.target.value };
                        onUpdateBlock(blk.id, { rows: updated } as any);
                      }}
                      className="w-28 bg-white border border-slate-300 rounded px-1 py-0.5 text-[10.5px]"
                    />
                    <select
                      value={row.variableId}
                      onChange={(e) => {
                        const updated = [...blk.rows];
                        updated[rIdx] = { ...row, variableId: e.target.value };
                        onUpdateBlock(blk.id, { rows: updated } as any);
                      }}
                      className="flex-1 bg-white border border-slate-300 rounded px-1 py-0.5 text-[10px] font-mono"
                    >
                      {AVAILABLE_VARIABLES.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.id}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => {
                        const updated = blk.rows.filter((_, idx) => idx !== rIdx);
                        onUpdateBlock(blk.id, { rows: updated } as any);
                      }}
                      className="p-1 text-slate-400 hover:text-red-600"
                    >
                      <Trash size={10} />
                    </button>
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={() => {
                  const newRow = {
                    id: `r_${Date.now()}`,
                    label: "New Spec",
                    variableId: "vehicle_no",
                  };
                  onUpdateBlock(blk.id, { rows: [...blk.rows, newRow] } as any);
                }}
                className="w-full py-1 text-xs font-semibold text-blue-700 border border-blue-200 rounded hover:bg-blue-50"
              >
                + Add Spec Row
              </button>
            </div>
          )}

          {/* PREMIUM BREAKDOWN */}
          {blk.type === "premium_block" && (
            <div className="space-y-2 text-[11px]">
              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">Premium Label:</label>
                <input
                  type="text"
                  value={blk.premiumLabel || "Insurance Premium"}
                  onChange={(e) => onUpdateBlock(blk.id, { premiumLabel: e.target.value } as any)}
                  className="w-full bg-white border border-slate-300 rounded p-1 text-xs"
                />
              </div>
              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">Combined Roadtax & Runner Label:</label>
                <input
                  type="text"
                  value={blk.roadtaxLabel || "Roadtax and Runner Fee / 路税及服务费"}
                  onChange={(e) => onUpdateBlock(blk.id, { roadtaxLabel: e.target.value } as any)}
                  className="w-full bg-white border border-slate-300 rounded p-1 text-xs"
                />
              </div>
              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">Total Payable Label:</label>
                <input
                  type="text"
                  value={blk.totalLabel || "Total Payable / 总付金额"}
                  onChange={(e) => onUpdateBlock(blk.id, { totalLabel: e.target.value } as any)}
                  className="w-full bg-white border border-slate-300 rounded p-1 text-xs"
                />
              </div>
            </div>
          )}

          {/* BENEFITS GRID */}
          {blk.type === "benefits_grid" && (
            <div className="space-y-2 text-[11px]">
              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">Section Title:</label>
                <input
                  type="text"
                  value={blk.titleEn || "Comprehensive Benefits"}
                  onChange={(e) => onUpdateBlock(blk.id, { titleEn: e.target.value } as any)}
                  className="w-full bg-white border border-slate-300 rounded p-1 text-xs"
                />
              </div>
              <div>
                <label className="text-slate-700 font-semibold block mb-0.5">Columns Count:</label>
                <div className="grid grid-cols-3 gap-1">
                  {[2, 3, 4].map((col) => (
                    <button
                      key={col}
                      type="button"
                      onClick={() => onUpdateBlock(blk.id, { columns: col } as any)}
                      className={`py-1 rounded border font-semibold ${
                        blk.columns === col
                          ? "bg-blue-600 text-white border-blue-600"
                          : "bg-white text-slate-600 border-slate-200"
                      }`}
                    >
                      {col} Cols
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      );
    }

    return null;
  }

  return (
    <aside className="w-[340px] shrink-0 border-l border-slate-200 bg-white flex flex-col h-full overflow-hidden select-none">
      {/* Top View Mode Switcher */}
      <div className="flex border-b border-slate-200 bg-slate-50/90 p-1 shrink-0">
        <button
          type="button"
          onClick={() => setViewMode("split")}
          className={`flex-1 py-1.5 rounded text-[11px] font-bold transition-all text-center flex items-center justify-center gap-1 ${
            viewMode === "split"
              ? "bg-white text-blue-700 shadow-xs ring-1 ring-slate-200"
              : "text-slate-500 hover:text-slate-800"
          }`}
          title="Show both Structure Tree and Properties"
        >
          <SplitHorizontal size={12} weight="bold" />
          Split View
        </button>
        <button
          type="button"
          onClick={() => setViewMode("structure")}
          className={`flex-1 py-1.5 rounded text-[11px] font-bold transition-all text-center ${
            viewMode === "structure"
              ? "bg-white text-blue-700 shadow-xs ring-1 ring-slate-200"
              : "text-slate-500 hover:text-slate-800"
          }`}
          title="Hierarchy tree only"
        >
          Structure
        </button>
        <button
          type="button"
          onClick={() => setViewMode("properties")}
          className={`flex-1 py-1.5 rounded text-[11px] font-bold transition-all text-center ${
            viewMode === "properties"
              ? "bg-white text-blue-700 shadow-xs ring-1 ring-slate-200"
              : "text-slate-500 hover:text-slate-800"
          }`}
          title="Properties & CSS only"
        >
          Properties
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
        {/* MODE: SPLIT VIEW (Both visible at once) */}
        {viewMode === "split" && (
          <div className="flex-1 flex flex-col min-h-0 divide-y divide-slate-200">
            {/* Top Half: Hierarchy Structure Tree */}
            <div className="flex-1 min-h-[180px] max-h-[48%] overflow-y-auto p-2.5 bg-slate-50/40">
              {renderStructureTree()}
            </div>

            {/* Bottom Half: Properties of Selected Item */}
            <div className="flex-1 min-h-[220px] overflow-y-auto p-3 bg-white">
              {renderPropertiesInspector()}
            </div>
          </div>
        )}

        {/* MODE: STRUCTURE ONLY */}
        {viewMode === "structure" && (
          <div className="flex-1 overflow-y-auto p-3">
            {renderStructureTree()}
          </div>
        )}

        {/* MODE: PROPERTIES ONLY */}
        {viewMode === "properties" && (
          <div className="flex-1 overflow-y-auto p-3">
            {renderPropertiesInspector()}
          </div>
        )}
      </div>
    </aside>
  );
}
