"use client";

import React from "react";
import { Check } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PerilsChecklistEditor } from "./PerilsChecklistEditor";

export function InlineDatePeriodPanel({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
  onSave,
  saving,
}: {
  startDate: string;
  endDate: string;
  onStartDateChange: (val: string) => void;
  onEndDateChange: (val: string) => void;
  onSave: () => void;
  saving: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="text-[10px] font-bold uppercase text-[#6e6e73] block mb-0.5">
            Start
          </label>
          <Input
            type="date"
            value={startDate}
            onChange={(e) => onStartDateChange(e.target.value)}
            className="h-8 text-[11px] font-mono rounded-[var(--rl-radius-sm)]"
          />
        </div>
        <div>
          <label className="text-[10px] font-bold uppercase text-[#6e6e73] block mb-0.5">
            End
          </label>
          <Input
            type="date"
            value={endDate}
            onChange={(e) => onEndDateChange(e.target.value)}
            className="h-8 text-[11px] font-mono rounded-[var(--rl-radius-sm)]"
          />
        </div>
      </div>
      <Button type="button" variant="primary" size="sm" loading={saving} onClick={onSave} className="w-full">
        <Check size={12} weight="bold" />
        Save Period
      </Button>
    </div>
  );
}

export function InlinePerilsPanel({
  perils,
  onChange,
  onSave,
  saving,
}: {
  perils: string[];
  onChange: (next: string[]) => void;
  onSave: () => void;
  saving: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="max-h-52 overflow-y-auto pr-0.5">
        <PerilsChecklistEditor selectedPerils={perils} onChange={onChange} compact />
      </div>
      <Button type="button" variant="primary" size="sm" loading={saving} onClick={onSave} className="w-full">
        <Check size={12} weight="bold" />
        Save Perils
      </Button>
    </div>
  );
}

export function InlineFixedCostsPanel({
  incRt,
  incRf,
  rtDraft,
  rfDraft,
  onIncRtChange,
  onIncRfChange,
  onRtChange,
  onRfChange,
  onSave,
  saving,
}: {
  incRt: boolean;
  incRf: boolean;
  rtDraft: string;
  rfDraft: string;
  onIncRtChange: (val: boolean) => void;
  onIncRfChange: (val: boolean) => void;
  onRtChange: (val: string) => void;
  onRfChange: (val: string) => void;
  onSave: () => void;
  saving: boolean;
}) {
  return (
    <div className="space-y-2">
      <div className="space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <label className="text-[11px] font-semibold text-[#1b1717] flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={incRt} onChange={(e) => onIncRtChange(e.target.checked)} />
            Road Tax (RM)
          </label>
          <Input
            type="number"
            step="0.01"
            min={0}
            value={rtDraft}
            onChange={(e) => onRtChange(e.target.value)}
            className="h-7 w-24 text-[11px] font-mono rounded-[var(--rl-radius-sm)]"
          />
        </div>
        <div className="flex items-center justify-between gap-2">
          <label className="text-[11px] font-semibold text-[#1b1717] flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" checked={incRf} onChange={(e) => onIncRfChange(e.target.checked)} />
            Runner Fee (RM)
          </label>
          <Input
            type="number"
            step="0.01"
            min={0}
            value={rfDraft}
            onChange={(e) => onRfChange(e.target.value)}
            className="h-7 w-24 text-[11px] font-mono rounded-[var(--rl-radius-sm)]"
          />
        </div>
      </div>
      <Button type="button" variant="primary" size="sm" loading={saving} onClick={onSave} className="w-full">
        <Check size={12} weight="bold" />
        Save Fixed Costs
      </Button>
    </div>
  );
}
