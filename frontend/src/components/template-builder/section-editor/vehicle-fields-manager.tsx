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
import { Badge } from "@/components/ui/badge";
import { AddFieldDialog } from "./add-field-dialog";
import type { VehicleSpecFieldSlot } from "@/lib/template-section-compiler";

interface VehicleFieldsManagerProps {
  fields: VehicleSpecFieldSlot[];
  onChange: (updatedFields: VehicleSpecFieldSlot[]) => void;
}

export function VehicleFieldsManager({ fields, onChange }: VehicleFieldsManagerProps) {
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [editingFieldId, setEditingFieldId] = useState<string | null>(null);
  const [editLabelEn, setEditLabelEn] = useState("");
  const [editLabelZh, setEditLabelZh] = useState("");

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

  const handleAddField = (slot: VehicleSpecFieldSlot) => {
    const updated = [
      ...sortedFields,
      { ...slot, rowOrder: sortedFields.length },
    ];
    onChange(updated);
  };

  const startEdit = (field: VehicleSpecFieldSlot) => {
    setEditingFieldId(field.id);
    setEditLabelEn(field.labelEn);
    setEditLabelZh(field.labelZh || "");
  };

  const saveEdit = (id: string) => {
    const updated = sortedFields.map((f) => {
      if (f.id === id) {
        return {
          ...f,
          labelEn: editLabelEn.trim() || f.labelEn,
          labelZh: editLabelZh.trim() || undefined,
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
            {sortedFields.filter((f) => f.visible).length} visible fields • Section 1 auto-aligns without pixel dragging
          </p>
        </div>
        <Button
          size="sm"
          variant="primary"
          onClick={() => setIsAddOpen(true)}
          className="gap-1.5 shadow-sm"
        >
          <Plus size={14} weight="bold" />
          Add Field
        </Button>
      </div>

      {/* Field List */}
      <div className="space-y-2">
        {sortedFields.map((field, index) => {
          const isEditing = editingFieldId === field.id;

          return (
            <div
              key={field.id}
              className={`flex flex-col gap-2 p-3 rounded-[var(--rl-radius)] border transition-all ${
                field.visible
                  ? "bg-[var(--rl-surface)] border-[var(--rl-border)] hover:border-neutral-300"
                  : "bg-neutral-50/80 border-dashed border-neutral-200 opacity-60"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                {/* Left side: Order badge & Field identification */}
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <span className="flex items-center justify-center w-5 h-5 rounded-full bg-[var(--rl-bg)] text-[10px] font-bold text-[var(--rl-text-muted)] shrink-0">
                    {index + 1}
                  </span>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs font-bold text-[var(--rl-text-strong)] truncate">
                        {field.labelEn}
                        {field.labelZh && (
                          <span className="text-[var(--rl-text-muted)] font-normal ml-1">
                            / {field.labelZh}
                          </span>
                        )}
                      </span>
                      {field.variableId ? (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-blue-50 text-blue-700 border border-blue-200">
                          {field.variableId}
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-mono bg-amber-50 text-amber-700 border border-amber-200">
                          static: {field.fixedValue || "empty"}
                        </span>
                      )}
                      {field.prefix && (
                        <span className="text-[10px] text-neutral-500 font-mono">
                          [{field.prefix}...]
                        </span>
                      )}
                      {field.suffix && (
                        <span className="text-[10px] text-neutral-500 font-mono">
                          [...{field.suffix}]
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right side: Reorder & Actions */}
                <div className="flex items-center gap-1 shrink-0">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleMove(index, "up")}
                    disabled={index === 0}
                    className="p-1 h-7 w-7 text-neutral-500 disabled:opacity-20"
                    title="Move Up"
                  >
                    <CaretUp size={14} weight="bold" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleMove(index, "down")}
                    disabled={index === sortedFields.length - 1}
                    className="p-1 h-7 w-7 text-neutral-500 disabled:opacity-20"
                    title="Move Down"
                  >
                    <CaretDown size={14} weight="bold" />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => startEdit(field)}
                    className="p-1 h-7 w-7 text-neutral-600 hover:text-blue-600"
                    title="Edit Label"
                  >
                    <PencilSimple size={14} />
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleToggleVisible(field.id)}
                    className={`p-1 h-7 w-7 ${
                      field.visible ? "text-neutral-600" : "text-neutral-400"
                    }`}
                    title={field.visible ? "Hide field" : "Show field"}
                  >
                    {field.visible ? <Eye size={14} /> : <EyeClosed size={14} />}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleDelete(field.id)}
                    className="p-1 h-7 w-7 text-neutral-400 hover:text-red-600"
                    title="Remove field"
                  >
                    <Trash size={14} />
                  </Button>
                </div>
              </div>

              {/* Inline label editor */}
              {isEditing && (
                <div className="mt-2 pt-2 border-t border-[var(--rl-border)] flex items-center gap-2 text-xs animate-fade-in">
                  <Input
                    value={editLabelEn}
                    onChange={(e) => setEditLabelEn(e.target.value)}
                    placeholder="English Label"
                    className="h-7 text-xs flex-1"
                  />
                  <Input
                    value={editLabelZh}
                    onChange={(e) => setEditLabelZh(e.target.value)}
                    placeholder="Chinese Label (optional)"
                    className="h-7 text-xs flex-1"
                  />
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => saveEdit(field.id)}
                    className="h-7 px-2 text-xs"
                  >
                    Save
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setEditingFieldId(null)}
                    className="h-7 px-2 text-xs"
                  >
                    Cancel
                  </Button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <AddFieldDialog
        open={isAddOpen}
        onOpenChange={setIsAddOpen}
        onAddField={handleAddField}
        existingFieldIds={existingFieldIds}
      />
    </div>
  );
}
