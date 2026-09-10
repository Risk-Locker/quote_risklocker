"use client";

import { useState } from "react";
import { Dialog } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  AVAILABLE_VARIABLES,
  type VehicleSpecFieldSlot,
  type VariableDescriptor,
} from "@/lib/template-section-compiler";

interface AddFieldDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onAddField: (slot: VehicleSpecFieldSlot) => void;
  existingFieldIds: Set<string>;
}

export function AddFieldDialog({
  open,
  onOpenChange,
  onAddField,
  existingFieldIds,
}: AddFieldDialogProps) {
  const [selectedVariableId, setSelectedVariableId] = useState<string>("engine_cc");
  const [isCustom, setIsCustom] = useState<boolean>(false);
  const [customKey, setCustomKey] = useState<string>("");
  const [labelEn, setLabelEn] = useState<string>("Engine CC / Capacity");
  const [labelZh, setLabelZh] = useState<string>("发动机排量");
  const [prefix, setPrefix] = useState<string>("");
  const [suffix, setSuffix] = useState<string>("");
  const [fixedValue, setFixedValue] = useState<string>("");

  const handleVariableChange = (varId: string) => {
    if (varId === "custom") {
      setIsCustom(true);
      setSelectedVariableId("");
      setLabelEn("Custom Field");
      setLabelZh("");
      setPrefix("");
      setSuffix("");
      return;
    }

    setIsCustom(false);
    setSelectedVariableId(varId);
    const desc = AVAILABLE_VARIABLES.find((v) => v.variableId === varId);
    if (desc) {
      setLabelEn(desc.labelEn);
      setLabelZh(desc.labelZh);
      setPrefix(desc.defaultPrefix || "");
      setSuffix(desc.defaultSuffix || "");
    }
  };

  const handleConfirm = () => {
    const rawId = isCustom ? customKey.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_") : selectedVariableId;
    if (!rawId) return;

    let uniqueId = rawId;
    let counter = 1;
    while (existingFieldIds.has(uniqueId)) {
      uniqueId = `${rawId}_${counter}`;
      counter++;
    }

    const slot: VehicleSpecFieldSlot = {
      id: uniqueId,
      variableId: isCustom ? undefined : selectedVariableId,
      labelEn: labelEn.trim() || rawId,
      labelZh: labelZh.trim() || undefined,
      prefix: prefix.trim() || undefined,
      suffix: suffix.trim() || undefined,
      fixedValue: isCustom ? fixedValue.trim() || undefined : undefined,
      visible: true,
      rowOrder: 999, // Will be appended at the end
    };

    onAddField(slot);
    onOpenChange(false);
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Add Field to Specifications"
      description="Select an extracted policy/vehicle variable or create a custom static field to add to Section 1."
      confirmLabel="Add Field"
      onConfirm={handleConfirm}
    >
      <div className="space-y-4 pt-2 text-xs">
        <div>
          <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
            Field Source
          </label>
          <Select
            value={isCustom ? "custom" : selectedVariableId}
            onChange={(e) => handleVariableChange(e.target.value)}
            className="w-full"
          >
            <optgroup label="Vehicle Specifications">
              {AVAILABLE_VARIABLES.filter((v) => v.category === "vehicle").map((v) => (
                <option key={v.variableId} value={v.variableId}>
                  {v.labelEn} ({v.variableId})
                </option>
              ))}
            </optgroup>
            <optgroup label="Policy Details">
              {AVAILABLE_VARIABLES.filter((v) => v.category === "policy").map((v) => (
                <option key={v.variableId} value={v.variableId}>
                  {v.labelEn} ({v.variableId})
                </option>
              ))}
            </optgroup>
            <optgroup label="Pricing & Totals">
              {AVAILABLE_VARIABLES.filter((v) => v.category === "pricing").map((v) => (
                <option key={v.variableId} value={v.variableId}>
                  {v.labelEn} ({v.variableId})
                </option>
              ))}
            </optgroup>
            <optgroup label="Custom">
              <option value="custom">Custom Static Field...</option>
            </optgroup>
          </Select>
        </div>

        {isCustom && (
          <div className="space-y-3 rounded border border-amber-200 bg-amber-50/50 p-3">
            <div>
              <label className="block font-medium text-amber-900 mb-1">
                Custom Field Key (ID)
              </label>
              <Input
                value={customKey}
                onChange={(e) => setCustomKey(e.target.value)}
                placeholder="e.g. chassis_no, seating"
                className="bg-white"
              />
            </div>
            <div>
              <label className="block font-medium text-amber-900 mb-1">
                Fixed Text Value (Optional)
              </label>
              <Input
                value={fixedValue}
                onChange={(e) => setFixedValue(e.target.value)}
                placeholder="e.g. 5 Seater, N/A"
                className="bg-white"
              />
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
              Label (English)
            </label>
            <Input
              value={labelEn}
              onChange={(e) => setLabelEn(e.target.value)}
              placeholder="e.g. Engine CC"
            />
          </div>
          <div>
            <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
              Label (Chinese / Secondary)
            </label>
            <Input
              value={labelZh}
              onChange={(e) => setLabelZh(e.target.value)}
              placeholder="e.g. 发动机排量"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
              Prefix (e.g. RM )
            </label>
            <Input
              value={prefix}
              onChange={(e) => setPrefix(e.target.value)}
              placeholder="e.g. RM "
            />
          </div>
          <div>
            <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
              Suffix (e.g. %)
            </label>
            <Input
              value={suffix}
              onChange={(e) => setSuffix(e.target.value)}
              placeholder="e.g. %"
            />
          </div>
        </div>
      </div>
    </Dialog>
  );
}
