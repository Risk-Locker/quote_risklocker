"use client";

import { useMemo, useState } from "react";
import {
  CaretDown,
  CaretUp,
  Eye,
  EyeClosed,
  Image as ImageIcon,
  Minus,
  PencilSimple,
  Plus,
  TextAa,
  Trash,
  BracketsCurly as VariableIcon,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  AVAILABLE_VARIABLES,
  type ContainerBlockConfig,
  type GenericBlockConfig,
  type GenericBlockType,
} from "@/lib/template-section-compiler";

interface RightContainerManagerProps {
  containers: ContainerBlockConfig[];
  onChange: (updatedContainers: ContainerBlockConfig[]) => void;
}

export function RightContainerManager({
  containers,
  onChange,
}: RightContainerManagerProps) {
  const [activeContainerId, setActiveContainerId] = useState<string>(
    containers[0]?.id || "rc_container_payment"
  );

  const fallbackContainer: ContainerBlockConfig = {
    id: "rc_container_payment",
    title: "Payment Method Card",
    layout: "column",
    boxX: 508,
    boxY: 134,
    boxW: 246,
    boxH: 92,
    background: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E2E8F0",
    borderRadius: 6,
    padding: 10,
    gap: 4,
    blocks: [],
  };

  const activeContainer =
    containers.find((c) => c.id === activeContainerId) ||
    containers[0] ||
    fallbackContainer;

  const [editingBlockId, setEditingBlockId] = useState<string | null>(null);
  const [editBlockDraft, setEditBlockDraft] = useState<Partial<GenericBlockConfig>>({});
  const [isAddMenuOpen, setIsAddMenuOpen] = useState(false);

  const sortedBlocks = useMemo(() => {
    return [...(activeContainer.blocks || [])].sort(
      (a, b) => (a.order ?? 0) - (b.order ?? 0)
    );
  }, [activeContainer.blocks]);

  const updateActiveContainer = (patch: Partial<ContainerBlockConfig>) => {
    const baseList = containers.length > 0 ? containers : [activeContainer];
    const updated = baseList.map((c) =>
      c.id === activeContainer.id ? { ...c, ...patch } : c
    );
    onChange(updated);
  };

  const handleMoveBlock = (index: number, direction: "up" | "down") => {
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= sortedBlocks.length) return;

    const reordered = [...sortedBlocks];
    const [moved] = reordered.splice(index, 1);
    reordered.splice(targetIndex, 0, moved);

    const updatedBlocks = reordered.map((item, idx) => ({
      ...item,
      order: idx,
    }));

    updateActiveContainer({ blocks: updatedBlocks });
  };

  const handleToggleVisible = (blockId: string) => {
    const updatedBlocks = sortedBlocks.map((b) => {
      if (b.id === blockId) {
        return { ...b, visible: b.visible === false ? true : false };
      }
      return b;
    });
    updateActiveContainer({ blocks: updatedBlocks });
  };

  const handleDeleteBlock = (blockId: string) => {
    const remaining = sortedBlocks
      .filter((b) => b.id !== blockId)
      .map((item, idx) => ({
        ...item,
        order: idx,
      }));
    updateActiveContainer({ blocks: remaining });
    if (editingBlockId === blockId) {
      setEditingBlockId(null);
    }
  };

  const handleAddBlock = (type: GenericBlockType) => {
    const newId = `rc_b_${Date.now()}`;
    let newBlock: GenericBlockConfig;

    if (type === "image") {
      newBlock = {
        id: newId,
        type: "image",
        assetSlot: "bank_logo",
        imageWidth: 100,
        imageHeight: 24,
        imageFit: "contain",
        visible: true,
        order: sortedBlocks.length,
      };
    } else if (type === "text") {
      newBlock = {
        id: newId,
        type: "text",
        text: "Custom note or payment detail",
        fontSize: 9.5,
        fontWeight: "500",
        color: "#0F172A",
        textAlign: "left",
        visible: true,
        order: sortedBlocks.length,
      };
    } else if (type === "variable") {
      newBlock = {
        id: newId,
        type: "variable",
        variableId: "excess_amount",
        prefix: "Excess: RM ",
        fontSize: 9.5,
        fontWeight: "700",
        color: "#0F172A",
        textAlign: "left",
        visible: true,
        order: sortedBlocks.length,
      };
    } else {
      // Divider
      newBlock = {
        id: newId,
        type: "divider",
        dividerColor: "#E2E8F0",
        dividerHeight: 1,
        visible: true,
        order: sortedBlocks.length,
      };
    }

    const updatedBlocks = [...sortedBlocks, newBlock];
    updateActiveContainer({ blocks: updatedBlocks });
    setEditingBlockId(newId);
    setEditBlockDraft(newBlock);
    setIsAddMenuOpen(false);
  };

  const startEdit = (block: GenericBlockConfig) => {
    setEditingBlockId(block.id);
    setEditBlockDraft({ ...block });
  };

  const saveEdit = (blockId: string) => {
    const updatedBlocks = sortedBlocks.map((b) => {
      if (b.id === blockId) {
        return {
          ...b,
          ...editBlockDraft,
        };
      }
      return b;
    });
    updateActiveContainer({ blocks: updatedBlocks });
    setEditingBlockId(null);
  };

  return (
    <div className="space-y-4 text-xs">
      {/* Container Settings Header */}
      <div className="pb-3 border-b border-[var(--rl-border)]">
        <h4 className="text-sm font-bold text-[var(--rl-text-strong)]">
          Right Container (Modular Cards)
        </h4>
        <p className="text-xs text-[var(--rl-text-muted)]">
          Manage each card (Payment Method, DuitNow QR, All Drivers & Excess) independently with zero overlaps.
        </p>
      </div>

      {/* Container Selector Tabs (when multiple cards exist) */}
      {containers.length > 1 && (
        <div className="flex items-center gap-1.5 p-1 bg-neutral-100 rounded-lg border border-neutral-200">
          {containers.map((c, idx) => {
            const isSelected = activeContainer.id === c.id;
            return (
              <button
                key={c.id || idx}
                type="button"
                onClick={() => {
                  setActiveContainerId(c.id);
                  setEditingBlockId(null);
                }}
                className={`flex-1 py-1.5 px-2 rounded text-[11px] font-semibold transition-all ${
                  isSelected
                    ? "bg-white text-[var(--rl-primary)] shadow-xs font-bold"
                    : "text-neutral-600 hover:text-neutral-900"
                }`}
              >
                {c.title || `Card ${idx + 1}`}
              </button>
            );
          })}
        </div>
      )}

      {/* Container Layout & Styling Controls */}
      <div className="p-3 rounded-lg border border-[var(--rl-border)] bg-neutral-50/50 space-y-3">
        <div className="flex items-center justify-between">
          <label className="font-bold text-[var(--rl-text-strong)]">Container Layout Flow</label>
          <div className="flex rounded-md border border-neutral-300 p-0.5 bg-white text-[11px]">
            <button
              type="button"
              onClick={() => updateActiveContainer({ layout: "column" })}
              className={`px-2 py-0.5 rounded transition-all font-semibold ${
                activeContainer.layout !== "row"
                  ? "bg-[var(--rl-primary)] text-white shadow-xs"
                  : "text-neutral-600 hover:text-black"
              }`}
            >
              Vertical (flex-col)
            </button>
            <button
              type="button"
              onClick={() => updateActiveContainer({ layout: "row" })}
              className={`px-2 py-0.5 rounded transition-all font-semibold ${
                activeContainer.layout === "row"
                  ? "bg-[var(--rl-primary)] text-white shadow-xs"
                  : "text-neutral-600 hover:text-black"
              }`}
            >
              Horizontal (flex-row)
            </button>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="block text-[10px] font-semibold text-neutral-500 mb-1">
              Background
            </label>
            <div className="flex items-center gap-1.5">
              <input
                type="color"
                value={activeContainer.background || "#FFFFFF"}
                onChange={(e) => updateActiveContainer({ background: e.target.value })}
                className="w-6 h-6 rounded border border-neutral-300 cursor-pointer"
              />
              <Input
                value={activeContainer.background || "#FFFFFF"}
                onChange={(e) => updateActiveContainer({ background: e.target.value })}
                className="h-6 text-[11px] font-mono px-1 flex-1"
              />
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-semibold text-neutral-500 mb-1">
              Border Color
            </label>
            <div className="flex items-center gap-1.5">
              <input
                type="color"
                value={activeContainer.borderColor || "#E2E8F0"}
                onChange={(e) => updateActiveContainer({ borderColor: e.target.value })}
                className="w-6 h-6 rounded border border-neutral-300 cursor-pointer"
              />
              <Input
                value={activeContainer.borderColor || "#E2E8F0"}
                onChange={(e) => updateActiveContainer({ borderColor: e.target.value })}
                className="h-6 text-[11px] font-mono px-1 flex-1"
              />
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-semibold text-neutral-500 mb-1">
              Corner Radius
            </label>
            <Select
              value={String(activeContainer.borderRadius ?? 6)}
              onChange={(e) => updateActiveContainer({ borderRadius: Number(e.target.value) })}
              className="h-6 text-[11px]"
            >
              <option value="0">0px (Square)</option>
              <option value="4">4px</option>
              <option value="6">6px</option>
              <option value="8">8px</option>
              <option value="12">12px</option>
            </Select>
          </div>
        </div>
      </div>

      {/* Blocks List Header & Add Block Buttons */}
      <div className="flex items-center justify-between pt-1">
        <div>
          <span className="font-bold text-[var(--rl-text-strong)]">
            Blocks Inside Container ({sortedBlocks.filter((b) => b.visible !== false).length})
          </span>
          <p className="text-[10px] text-[var(--rl-text-muted)]">
            Auto-flows without pixel overlap. Drag/reorder to change sequence.
          </p>
        </div>

        <div className="relative">
          <Button
            size="sm"
            variant="primary"
            onClick={() => setIsAddMenuOpen(!isAddMenuOpen)}
            className="gap-1 h-7 text-xs shadow-sm"
          >
            <Plus size={13} weight="bold" />
            Add Block
          </Button>

          {isAddMenuOpen && (
            <div className="absolute right-0 mt-1 w-44 rounded-md border border-[var(--rl-border)] bg-white shadow-lg z-20 py-1 text-xs animate-fade-in">
              <button
                type="button"
                onClick={() => handleAddBlock("text")}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-neutral-700 hover:bg-neutral-100 font-medium"
              >
                <TextAa size={14} className="text-blue-600" />
                Text Block
              </button>
              <button
                type="button"
                onClick={() => handleAddBlock("variable")}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-neutral-700 hover:bg-neutral-100 font-medium"
              >
                <VariableIcon size={14} className="text-emerald-600" />
                Variable Block
              </button>
              <button
                type="button"
                onClick={() => handleAddBlock("image")}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-neutral-700 hover:bg-neutral-100 font-medium"
              >
                <ImageIcon size={14} className="text-purple-600" />
                Image / QR Block
              </button>
              <button
                type="button"
                onClick={() => handleAddBlock("divider")}
                className="w-full flex items-center gap-2 px-3 py-1.5 text-left text-neutral-700 hover:bg-neutral-100 font-medium"
              >
                <Minus size={14} className="text-neutral-500" />
                Divider Line
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Quick 1-Click Add Action Bar */}
      <div className="grid grid-cols-4 gap-1.5 pt-1 pb-1">
        <button
          type="button"
          onClick={() => handleAddBlock("text")}
          className="flex items-center justify-center gap-1 py-1.5 px-1 rounded border border-blue-200 bg-blue-50/70 hover:bg-blue-100 text-blue-700 font-semibold text-[11px] transition-all shadow-2xs"
          title="Add a custom text label or notes block"
        >
          <Plus size={11} weight="bold" /> Text
        </button>
        <button
          type="button"
          onClick={() => handleAddBlock("variable")}
          className="flex items-center justify-center gap-1 py-1.5 px-1 rounded border border-emerald-200 bg-emerald-50/70 hover:bg-emerald-100 text-emerald-700 font-semibold text-[11px] transition-all shadow-2xs"
          title="Add a dynamic policy variable block"
        >
          <Plus size={11} weight="bold" /> Variable
        </button>
        <button
          type="button"
          onClick={() => handleAddBlock("image")}
          className="flex items-center justify-center gap-1 py-1.5 px-1 rounded border border-purple-200 bg-purple-50/70 hover:bg-purple-100 text-purple-700 font-semibold text-[11px] transition-all shadow-2xs"
          title="Add an image, bank logo, or QR code block"
        >
          <Plus size={11} weight="bold" /> Image/QR
        </button>
        <button
          type="button"
          onClick={() => handleAddBlock("divider")}
          className="flex items-center justify-center gap-1 py-1.5 px-1 rounded border border-neutral-200 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 font-semibold text-[11px] transition-all shadow-2xs"
          title="Add a horizontal divider line"
        >
          <Plus size={11} weight="bold" /> Line
        </button>
      </div>

      {/* Blocks List */}
      <div className="space-y-2">
        {sortedBlocks.map((block, index) => {
          const isEditing = editingBlockId === block.id;

          return (
            <div
              key={block.id}
              className={`flex flex-col gap-2 p-2.5 rounded-[var(--rl-radius)] border transition-all ${
                block.visible !== false
                  ? "bg-[var(--rl-surface)] border-[var(--rl-border)] hover:border-neutral-300"
                  : "bg-neutral-50 border-dashed border-neutral-200 opacity-60"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                {/* Left: Sequence index and block icon/preview */}
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-[var(--rl-bg)] text-[10px] font-bold text-[var(--rl-text-muted)] shrink-0">
                    {index + 1}
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {block.type === "image" && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-50 text-purple-700 border border-purple-200">
                          <ImageIcon size={11} />
                          Image: {block.assetSlot || "Custom"}
                        </span>
                      )}
                      {block.type === "text" && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-50 text-blue-700 border border-blue-200">
                          <TextAa size={11} />
                          Text ({block.fontSize || 9.5}px)
                        </span>
                      )}
                      {block.type === "variable" && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <VariableIcon size={11} />
                          Var: {block.variableId}
                        </span>
                      )}
                      {block.type === "divider" && (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-neutral-100 text-neutral-700 border border-neutral-200">
                          <Minus size={11} />
                          Divider Line
                        </span>
                      )}

                      <span className="text-[11px] text-neutral-600 truncate max-w-40 font-mono">
                        {block.type === "text" && (block.text || "Empty text")}
                        {block.type === "variable" && `${block.prefix || ""}{${block.variableId}}`}
                        {block.type === "image" && `${block.imageWidth || 100}x${block.imageHeight || 24}px`}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleMoveBlock(index, "up")}
                    disabled={index === 0}
                    className="p-1 h-6 w-6 text-neutral-500 disabled:opacity-20"
                    title="Move Up"
                  >
                    <CaretUp size={12} weight="bold" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleMoveBlock(index, "down")}
                    disabled={index === sortedBlocks.length - 1}
                    className="p-1 h-6 w-6 text-neutral-500 disabled:opacity-20"
                    title="Move Down"
                  >
                    <CaretDown size={12} weight="bold" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => (isEditing ? setEditingBlockId(null) : startEdit(block))}
                    className="p-1 h-6 w-6 text-neutral-600 hover:text-blue-600"
                    title="Edit Block"
                  >
                    <PencilSimple size={12} />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleToggleVisible(block.id)}
                    className={`p-1 h-6 w-6 ${
                      block.visible !== false ? "text-neutral-600" : "text-neutral-400"
                    }`}
                    title={block.visible !== false ? "Hide block" : "Show block"}
                  >
                    {block.visible !== false ? <Eye size={12} /> : <EyeClosed size={12} />}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDeleteBlock(block.id)}
                    className="p-1 h-6 w-6 text-neutral-400 hover:text-red-600"
                    title="Delete block"
                  >
                    <Trash size={12} />
                  </Button>
                </div>
              </div>

              {/* Inline Block Editor */}
              {isEditing && (
                <div className="mt-2 pt-2 border-t border-[var(--rl-border)] space-y-2.5 animate-fade-in bg-neutral-50/70 p-2 rounded">
                  {block.type === "text" && (
                    <div className="space-y-2">
                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                          Text Content (Multiline allowed)
                        </label>
                        <textarea
                          rows={2}
                          value={editBlockDraft.text ?? ""}
                          onChange={(e) =>
                            setEditBlockDraft((prev) => ({ ...prev, text: e.target.value }))
                          }
                          className="w-full text-xs rounded border border-neutral-300 p-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500 font-sans"
                        />
                      </div>

                      <div className="grid grid-cols-3 gap-2">
                        <div>
                          <label className="block text-[10px] font-semibold text-neutral-500 mb-0.5">
                            Font Size
                          </label>
                          <Input
                            type="number"
                            min={8}
                            max={24}
                            value={editBlockDraft.fontSize ?? 9.5}
                            onChange={(e) =>
                              setEditBlockDraft((prev) => ({
                                ...prev,
                                fontSize: Number(e.target.value),
                              }))
                            }
                            className="h-6 text-xs"
                          />
                        </div>

                        <div>
                          <label className="block text-[10px] font-semibold text-neutral-500 mb-0.5">
                            Weight
                          </label>
                          <Select
                            value={String(editBlockDraft.fontWeight ?? "500")}
                            onChange={(e) =>
                              setEditBlockDraft((prev) => ({
                                ...prev,
                                fontWeight: e.target.value,
                              }))
                            }
                            className="h-6 text-xs"
                          >
                            <option value="400">Regular (400)</option>
                            <option value="500">Medium (500)</option>
                            <option value="700">Bold (700)</option>
                            <option value="800">Black (800)</option>
                          </Select>
                        </div>

                        <div>
                          <label className="block text-[10px] font-semibold text-neutral-500 mb-0.5">
                            Color
                          </label>
                          <div className="flex items-center gap-1">
                            <input
                              type="color"
                              value={editBlockDraft.color || "#0F172A"}
                              onChange={(e) =>
                                setEditBlockDraft((prev) => ({ ...prev, color: e.target.value }))
                              }
                              className="w-5 h-5 rounded cursor-pointer"
                            />
                            <Input
                              value={editBlockDraft.color || "#0F172A"}
                              onChange={(e) =>
                                setEditBlockDraft((prev) => ({ ...prev, color: e.target.value }))
                              }
                              className="h-6 text-[10px] font-mono px-1 flex-1"
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {block.type === "variable" && (
                    <div className="space-y-2">
                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                          Bound Policy Variable
                        </label>
                        <Select
                          value={editBlockDraft.variableId ?? "excess_amount"}
                          onChange={(e) =>
                            setEditBlockDraft((prev) => ({ ...prev, variableId: e.target.value }))
                          }
                          className="h-7 text-xs w-full"
                        >
                          {AVAILABLE_VARIABLES.map((v) => (
                            <option key={v.variableId} value={v.variableId}>
                              {v.labelEn} ({v.variableId})
                            </option>
                          ))}
                        </Select>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-[10px] font-semibold text-neutral-500 mb-0.5">
                            Prefix (Label before value)
                          </label>
                          <Input
                            value={editBlockDraft.prefix ?? ""}
                            onChange={(e) =>
                              setEditBlockDraft((prev) => ({ ...prev, prefix: e.target.value }))
                            }
                            placeholder="e.g. Policy Excess: RM "
                            className="h-6 text-xs"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold text-neutral-500 mb-0.5">
                            Suffix
                          </label>
                          <Input
                            value={editBlockDraft.suffix ?? ""}
                            onChange={(e) =>
                              setEditBlockDraft((prev) => ({ ...prev, suffix: e.target.value }))
                            }
                            placeholder="e.g. %"
                            className="h-6 text-xs"
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  {block.type === "image" && (
                    <div className="space-y-2">
                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                          Asset Slot
                        </label>
                        <Select
                          value={editBlockDraft.assetSlot ?? "bank_logo"}
                          onChange={(e) =>
                            setEditBlockDraft((prev) => ({ ...prev, assetSlot: e.target.value }))
                          }
                          className="h-7 text-xs w-full"
                        >
                          <option value="duitnow_payment_details">DuitNow Payment Details Card (duitnow_payment_details)</option>
                          <option value="bank_logo">Bank Logo (bank_logo)</option>
                          <option value="qr_code">Payment QR Code (qr_code)</option>
                          <option value="risklocker_logo">Risklocker Logo (risklocker_logo)</option>
                          <option value="all_driver_icon">All Driver Badge (all_driver_icon)</option>
                          <option value="custom_qr">Payment QR / Graphic (custom_qr)</option>
                        </Select>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-[10px] font-semibold text-neutral-500 mb-0.5">
                            Width (px)
                          </label>
                          <Input
                            type="number"
                            value={editBlockDraft.imageWidth ?? 100}
                            onChange={(e) =>
                              setEditBlockDraft((prev) => ({
                                ...prev,
                                imageWidth: Number(e.target.value),
                              }))
                            }
                            className="h-6 text-xs"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold text-neutral-500 mb-0.5">
                            Height (px)
                          </label>
                          <Input
                            type="number"
                            value={editBlockDraft.imageHeight ?? 24}
                            onChange={(e) =>
                              setEditBlockDraft((prev) => ({
                                ...prev,
                                imageHeight: Number(e.target.value),
                              }))
                            }
                            className="h-6 text-xs"
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  {block.type === "divider" && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-500 mb-0.5">
                          Divider Color
                        </label>
                        <Input
                          value={editBlockDraft.dividerColor ?? "#E2E8F0"}
                          onChange={(e) =>
                            setEditBlockDraft((prev) => ({
                              ...prev,
                              dividerColor: e.target.value,
                            }))
                          }
                          className="h-6 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-500 mb-0.5">
                          Thickness (px)
                        </label>
                        <Input
                          type="number"
                          min={1}
                          max={4}
                          value={editBlockDraft.dividerHeight ?? 1}
                          onChange={(e) =>
                            setEditBlockDraft((prev) => ({
                              ...prev,
                              dividerHeight: Number(e.target.value),
                            }))
                          }
                          className="h-6 text-xs"
                        />
                      </div>
                    </div>
                  )}

                  <div className="flex items-center justify-end gap-1.5 pt-1">
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => setEditingBlockId(null)}
                      className="h-6 px-2 text-xs"
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      onClick={() => saveEdit(block.id)}
                      className="h-6 px-2 text-xs"
                    >
                      Save Changes
                    </Button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
