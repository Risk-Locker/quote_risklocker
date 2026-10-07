"use client";

import { useMemo, useState } from "react";
import {
  CaretDown,
  CaretUp,
  Eye,
  EyeClosed,
  PencilSimple,
  Plus,
  Trash,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { AddFieldDialog } from "./add-field-dialog";
import {
  AVAILABLE_VARIABLES,
  type VehicleSpecFieldSlot,
} from "@/lib/template-section-compiler";

interface VehicleFieldsManagerProps {
  fields: VehicleSpecFieldSlot[];
  onChange: (updatedFields: VehicleSpecFieldSlot[]) => void;
  extrasDisplayMode?: "itemized" | "lump_sum" | "none";
  onExtrasDisplayModeChange?: (mode: "itemized" | "lump_sum" | "none") => void;
}

export function VehicleFieldsManager({
  fields,
  onChange,
  extrasDisplayMode = "itemized",
  onExtrasDisplayModeChange,
}: VehicleFieldsManagerProps) {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [targetInsertIndex, setTargetInsertIndex] = useState<number | null>(null);

  const [editingFieldId, setEditingFieldId] = useState<string | null>(null);
  const [editLabelEn, setEditLabelEn] = useState("");
  const [editLabelZh, setEditLabelZh] = useState("");
  const [editVariableId, setEditVariableId] = useState<string | undefined>("");
  const [editFontSize, setEditFontSize] = useState<number>(12);
  const [editFontWeight, setEditFontWeight] = useState<string>("700");
  const [editColor, setEditColor] = useState<string>("#111111");
  const [editPrefix, setEditPrefix] = useState<string>("");
  const [editSuffix, setEditSuffix] = useState<string>("");

  const sortedFields = useMemo(() => {
    return [...fields].sort((a, b) => a.rowOrder - b.rowOrder);
  }, [fields]);

  const existingFieldIds = useMemo(() => {
    return new Set(fields.map((f) => f.id));
  }, [fields]);

  const handleMove = (index: number, direction: "up" | "down") => {
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= sortedFields.length) return;

    const reordered = [...sortedFields];
    const [moved] = reordered.splice(index, 1);
    reordered.splice(targetIndex, 0, moved);

    const updated = reordered.map((item, idx) => ({
      ...item,
      rowOrder: idx,
    }));

    onChange(updated);
  };

  const handleMoveTo = (currentIndex: number, newIndex: number) => {
    if (newIndex < 0 || newIndex >= sortedFields.length || newIndex === currentIndex) return;
    const reordered = [...sortedFields];
    const [moved] = reordered.splice(currentIndex, 1);
    reordered.splice(newIndex, 0, moved);

    const updated = reordered.map((item, idx) => ({
      ...item,
      rowOrder: idx,
    }));

    onChange(updated);
  };

  const handleToggleVisible = (id: string) => {
    const updated = sortedFields.map((f) => {
      if (f.id === id) {
        return { ...f, visible: !f.visible };
      }
      return f;
    });
    onChange(updated);
  };

  const handleDelete = (id: string) => {
    const remaining = sortedFields
      .filter((f) => f.id !== id)
      .map((item, idx) => ({
        ...item,
        rowOrder: idx,
      }));
    onChange(remaining);
  };

  const handleAddField = (slot: VehicleSpecFieldSlot, insertAt?: number | null) => {
    const reordered = [...sortedFields];
    if (insertAt !== undefined && insertAt !== null && insertAt >= 0 && insertAt <= reordered.length) {
      reordered.splice(insertAt, 0, slot);
    } else {
      reordered.push(slot);
    }

    const updated = reordered.map((item, idx) => ({
      ...item,
      rowOrder: idx,
    }));
    onChange(updated);
    setTargetInsertIndex(null);
  };

  const openAddAt = (index: number | null) => {
    setTargetInsertIndex(index);
    setIsAddOpen(true);
  };

  const startEdit = (field: VehicleSpecFieldSlot) => {
    setEditingFieldId(field.id);
    setEditLabelEn(field.labelEn);
    setEditLabelZh(field.labelZh || "");
    setEditVariableId(field.variableId);
    setEditFontSize(field.fontSize ?? 12);
    setEditFontWeight(field.fontWeight ?? "700");
    setEditColor(field.color ?? "#111111");
    setEditPrefix(field.prefix ?? "");
    setEditSuffix(field.suffix ?? "");
  };

  const saveEdit = (id: string) => {
    const updated = sortedFields.map((f) => {
      if (f.id === id) {
        return {
          ...f,
          labelEn: editLabelEn.trim() || f.labelEn,
          labelZh: editLabelZh.trim() || undefined,
          variableId: editVariableId || undefined,
          fontSize: editFontSize,
          fontWeight: editFontWeight,
          color: editColor,
          prefix: editPrefix.trim() || undefined,
          suffix: editSuffix.trim() || undefined,
        };
      }
      return f;
    });
    onChange(updated);
    setEditingFieldId(null);
  };

  return (
    <div className="space-y-4">
      {/* Header bar with counter and Add Field button */}
      <div className="flex items-center justify-between pb-3 border-b border-[var(--rl-border)]">
        <div>
          <h4 className="text-sm font-bold text-[var(--rl-text-strong)]">
            Vehicle & Policy Specification Slots
          </h4>
          <p className="text-xs text-[var(--rl-text-muted)]">
            {sortedFields.filter((f) => f.visible).length} visible fields • Dynamic row insertion & auto-fitted spacing
          </p>
        </div>
        <Button
          size="sm"
          variant="primary"
          onClick={() => openAddAt(null)}
          className="gap-1.5 shadow-sm h-7 text-xs"
        >
          <Plus size={14} weight="bold" />
          Add Row
        </Button>
      </div>

      {/* Field List */}
      <div className="space-y-2">
        {sortedFields.map((field, index) => {
          const isEditing = editingFieldId === field.id;

          return (
            <div key={field.id} className="space-y-1">
              <div
                className={`flex flex-col gap-2 p-2.5 rounded-[var(--rl-radius)] border transition-all ${
                  field.visible
                    ? "bg-[var(--rl-surface)] border-[var(--rl-border)] hover:border-neutral-300"
                    : "bg-neutral-50/80 border-dashed border-neutral-200 opacity-60"
                }`}
              >
                {/* Row 1: Position jump + Field title on left; actions on right */}
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0 flex-1">
                    <select
                      value={index}
                      onChange={(e) => handleMoveTo(index, Number(e.target.value))}
                      className="h-6 px-1 text-[11px] font-bold text-center rounded border border-neutral-300 bg-neutral-100 hover:bg-neutral-200 cursor-pointer text-[var(--rl-text-strong)] transition-colors focus:ring-1 focus:ring-blue-500 shrink-0"
                      title={`Current position: Row ${index + 1}. Select to jump to another row (e.g. Row 1 or Row 4).`}
                    >
                      {sortedFields.map((_, i) => (
                        <option key={i} value={i}>
                          #{i + 1}
                        </option>
                      ))}
                    </select>

                    <span
                      className="text-xs font-bold text-[var(--rl-text-strong)] truncate"
                      title={`${field.labelEn}${field.labelZh ? ` / ${field.labelZh}` : ""}`}
                    >
                      {field.labelEn}
                      {field.labelZh && (
                        <span className="text-[var(--rl-text-muted)] font-normal ml-1">
                          / {field.labelZh}
                        </span>
                      )}
                    </span>
                  </div>

                  {/* Actions: Reorder up/down, Edit, Visibility, Delete */}
                  <div className="flex items-center gap-0.5 shrink-0">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleMove(index, "up")}
                      disabled={index === 0}
                      className="h-6 w-6 p-0 text-neutral-600 hover:text-neutral-900 border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-20 shrink-0 shadow-2xs"
                      title="Move Up 1 Row"
                    >
                      <CaretUp size={12} weight="bold" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleMove(index, "down")}
                      disabled={index === sortedFields.length - 1}
                      className="h-6 w-6 p-0 text-neutral-600 hover:text-neutral-900 border border-neutral-200 bg-white hover:bg-neutral-50 disabled:opacity-20 shrink-0 shadow-2xs"
                      title="Move Down 1 Row"
                    >
                      <CaretDown size={12} weight="bold" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => (isEditing ? setEditingFieldId(null) : startEdit(field))}
                      className="p-1 h-6 w-6 text-neutral-600 hover:text-blue-600"
                      title="Edit Row"
                    >
                      <PencilSimple size={12} />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleToggleVisible(field.id)}
                      className={`p-1 h-6 w-6 ${
                        field.visible ? "text-neutral-600" : "text-neutral-400"
                      }`}
                      title={field.visible ? "Hide field" : "Show field"}
                    >
                      {field.visible ? <Eye size={12} /> : <EyeClosed size={12} />}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDelete(field.id)}
                      className="p-1 h-6 w-6 text-neutral-400 hover:text-red-600"
                      title="Remove field"
                    >
                      <Trash size={12} />
                    </Button>
                  </div>
                </div>

                {/* Row 2: Metadata tags (indented below select) */}
                <div className="flex items-center gap-1.5 pl-7 text-[10px] flex-wrap">
                  {field.variableId ? (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded font-mono bg-blue-50 text-blue-700 border border-blue-200">
                      {field.variableId}
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded font-mono bg-amber-50 text-amber-700 border border-amber-200">
                      static: {field.fixedValue || "empty"}
                    </span>
                  )}
                  {field.fontSize && field.fontSize !== 12 && (
                    <span className="text-neutral-500 font-mono">
                      {field.fontSize}px
                    </span>
                  )}
                  {field.prefix && (
                    <span className="text-neutral-500 font-mono">
                      [{field.prefix}...]
                    </span>
                  )}
                  {field.suffix && (
                    <span className="text-neutral-500 font-mono">
                      [...{field.suffix}]
                    </span>
                  )}
                </div>

                {/* Inline Row Editor */}
                {isEditing && (
                  <div className="mt-2 pt-2 border-t border-[var(--rl-border)] space-y-2.5 animate-fade-in bg-neutral-50/70 p-2.5 rounded text-xs">
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                          English Label
                        </label>
                        <Input
                          value={editLabelEn}
                          onChange={(e) => setEditLabelEn(e.target.value)}
                          placeholder="English Label"
                          className="h-7 text-xs"
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                          Chinese Label (optional)
                        </label>
                        <Input
                          value={editLabelZh}
                          onChange={(e) => setEditLabelZh(e.target.value)}
                          placeholder="Chinese Label"
                          className="h-7 text-xs"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                          Bound Variable
                        </label>
                        <Select
                          value={editVariableId || ""}
                          onChange={(e) => setEditVariableId(e.target.value || undefined)}
                          className="h-7 text-xs w-full"
                        >
                          <option value="">Static (no variable)</option>
                          {AVAILABLE_VARIABLES.map((v) => (
                            <option key={v.variableId} value={v.variableId}>
                              {v.labelEn} ({v.variableId})
                            </option>
                          ))}
                        </Select>
                      </div>

                      <div className="grid grid-cols-2 gap-1.5">
                        <div>
                          <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                            Prefix
                          </label>
                          <Input
                            value={editPrefix}
                            onChange={(e) => setEditPrefix(e.target.value)}
                            placeholder="e.g. RM "
                            className="h-7 text-xs"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                            Suffix
                          </label>
                          <Input
                            value={editSuffix}
                            onChange={(e) => setEditSuffix(e.target.value)}
                            placeholder="e.g. %"
                            className="h-7 text-xs"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                          Font Size (px)
                        </label>
                        <Input
                          type="number"
                          min={8}
                          max={22}
                          value={editFontSize}
                          onChange={(e) => setEditFontSize(Number(e.target.value))}
                          className="h-7 text-xs"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                          Font Weight
                        </label>
                        <Select
                          value={editFontWeight}
                          onChange={(e) => setEditFontWeight(e.target.value)}
                          className="h-7 text-xs"
                        >
                          <option value="400">Regular (400)</option>
                          <option value="500">Medium (500)</option>
                          <option value="600">SemiBold (600)</option>
                          <option value="700">Bold (700)</option>
                          <option value="800">ExtraBold (800)</option>
                        </Select>
                      </div>

                      <div>
                        <label className="block text-[10px] font-semibold text-neutral-600 mb-0.5">
                          Text Color
                        </label>
                        <div className="flex items-center gap-1.5">
                          <input
                            type="color"
                            value={editColor}
                            onChange={(e) => setEditColor(e.target.value)}
                            className="w-6 h-6 rounded cursor-pointer border border-neutral-300"
                          />
                          <Input
                            value={editColor}
                            onChange={(e) => setEditColor(e.target.value)}
                            className="h-7 text-[11px] font-mono px-1 flex-1"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center justify-end gap-1.5 pt-1">
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => setEditingFieldId(null)}
                        className="h-6 px-2 text-xs"
                      >
                        Cancel
                      </Button>
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => saveEdit(field.id)}
                        className="h-6 px-2 text-xs"
                      >
                        Save Row
                      </Button>
                    </div>
                  </div>
                )}
              </div>

              {/* Dynamic Extras Anchor Banner below Insurance Premium */}
              {(field.variableId === "premium" || field.id === "premium" || field.id === "insurance_premium") && (
                <div className="my-2.5 p-3 rounded-lg border border-red-300 bg-red-50/80 text-red-950 shadow-xs space-y-2">
                  <div className="flex items-start gap-2 select-none">
                    <div className="w-5 h-5 rounded-full bg-red-600 text-white flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                      ⚡
                    </div>
                    <div className="text-[11px] leading-snug flex-1">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-red-900">Dynamic Extras Format</span>
                        <span className="text-[10px] px-1.5 py-0.5 font-bold uppercase rounded bg-red-200/70 text-red-800">
                          {extrasDisplayMode === "none" ? "No Extras" : (extrasDisplayMode === "lump_sum" ? "Lump Sum" : "Itemized")}
                        </span>
                      </div>
                      <p className="text-[10px] text-red-700 mt-0.5">
                        Controls how purchased add-ons appear below Insurance Premium on quotation documents.
                      </p>
                    </div>
                  </div>

                  {/* 3-Option Display Mode Toggle */}
                  <div className="grid grid-cols-3 gap-1.5 p-1 bg-red-100/70 rounded-md border border-red-200">
                    <button
                      type="button"
                      onClick={() => onExtrasDisplayModeChange?.("itemized")}
                      className={`px-2 py-1.5 text-xs font-semibold rounded transition-all text-left flex flex-col gap-0.5 ${
                        extrasDisplayMode === "itemized" || !extrasDisplayMode
                          ? "bg-white text-red-950 shadow-xs font-bold border border-red-200"
                          : "text-red-800 hover:bg-white/50"
                      }`}
                    >
                      <span className="flex items-center gap-1">
                        <span>📑</span>
                        <span>Itemized</span>
                      </span>
                      <span className="text-[9.5px] opacity-75 font-normal">
                        Extras : <br />
                        Driver Pa RM 300
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={() => onExtrasDisplayModeChange?.("lump_sum")}
                      className={`px-2 py-1.5 text-xs font-semibold rounded transition-all text-left flex flex-col gap-0.5 ${
                        extrasDisplayMode === "lump_sum"
                          ? "bg-white text-red-950 shadow-xs font-bold border border-red-200"
                          : "text-red-800 hover:bg-white/50"
                      }`}
                    >
                      <span className="flex items-center gap-1">
                        <span>💵</span>
                        <span>Lump Sum</span>
                      </span>
                      <span className="text-[9.5px] opacity-75 font-normal">
                        Extras : <br />
                        RM 300
                      </span>
                    </button>

                    <button
                      type="button"
                      onClick={() => onExtrasDisplayModeChange?.("none")}
                      className={`px-2 py-1.5 text-xs font-semibold rounded transition-all text-left flex flex-col gap-0.5 ${
                        extrasDisplayMode === "none"
                          ? "bg-white text-red-950 shadow-xs font-bold border border-red-200"
                          : "text-red-800 hover:bg-white/50"
                      }`}
                    >
                      <span className="flex items-center gap-1">
                        <span>🚫</span>
                        <span>No Extras</span>
                      </span>
                      <span className="text-[9.5px] opacity-75 font-normal">
                        Folded in <br />
                        Premium
                      </span>
                    </button>
                  </div>
                </div>
              )}

              {/* Dynamic row insertion button between rows */}
              <div className="flex items-center justify-center py-0.5 opacity-40 hover:opacity-100 transition-opacity">
                <button
                  type="button"
                  onClick={() => openAddAt(index + 1)}
                  className="flex items-center gap-1 text-[10px] font-semibold text-neutral-500 hover:text-[var(--rl-primary)] hover:bg-neutral-100 px-2 py-0.5 rounded border border-dashed border-neutral-200 transition-colors"
                >
                  <Plus size={10} weight="bold" />
                  Insert Row Below
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <AddFieldDialog
        open={isAddOpen}
        onOpenChange={setIsAddOpen}
        onAddField={handleAddField}
        existingFieldIds={existingFieldIds}
        targetIndex={targetInsertIndex}
      />
    </div>
  );
}
