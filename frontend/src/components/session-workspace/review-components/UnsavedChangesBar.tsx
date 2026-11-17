"use client";

import React, { useMemo, useState } from "react";
import { FloppyDisk, ArrowCounterClockwise, WarningCircle, X } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useWorkspaceActions } from "@/components/session-workspace/provider";
import type { MutationState } from "../types";

const PRICING_PATHS = new Set([
  "fields.premium",
  "fields.roadtax",
  "fields.service_fee",
  "fields.include_road_tax",
  "fields.include_runner_fee",
  "fields.total_amount",
  "options.include_road_tax",
  "options.include_runner_fee",
  "display_options",
]);

function humanizeDirtyPath(path: string): string {
  if (path === "display_options" || path.startsWith("options.")) return "Fee / Display options";
  if (path.startsWith("benefits") || path.startsWith("source_line")) return "Benefits / Extras";
  if (path === "catalog" || path === "package_tier") return "Catalog selection";
  if (path === "template_revision_id") return "Template";
  if (path.startsWith("fields.")) {
    const raw = path.slice("fields.".length);
    return raw
      .split("_")
      .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : ""))
      .join(" ");
  }
  return path;
}

export interface UnsavedChangesBarProps {
  mutation: MutationState;
  onSave: () => void | Promise<unknown>;
  onDiscard: () => void | Promise<unknown>;
  onRevertPath?: (path: string) => void;
}

export function UnsavedChangesBar({ mutation, onSave, onDiscard, onRevertPath }: UnsavedChangesBarProps) {
  const workspaceActions = useWorkspaceActions();
  const revertSinglePath = onRevertPath || workspaceActions?.revertOperation;
  const [discardDialogOpen, setDiscardDialogOpen] = useState(false);
  const [discarding, setDiscarding] = useState(false);

  const summary = useMemo(() => {
    const labels: string[] = [];
    const items: Array<{ path: string; label: string }> = [];
    const seen = new Set<string>();
    let affectsTotals = false;
    let userEditCount = 0;

    for (const path of mutation.dirtyPaths) {
      if (PRICING_PATHS.has(path) || path.startsWith("benefits")) {
        affectsTotals = true;
      }
      if (path === "fields.total_amount" && mutation.dirtyPaths.length > 1) {
        continue;
      }
      if (
        (path === "options.include_road_tax" && mutation.dirtyPaths.includes("fields.include_road_tax")) ||
        (path === "options.include_runner_fee" && mutation.dirtyPaths.includes("fields.include_runner_fee")) ||
        (["fields.coverage_amount", "fields.market_value", "fields.agreed_value"].includes(path) &&
          mutation.dirtyPaths.includes("fields.sum_insured"))
      ) {
        continue;
      }
      userEditCount += 1;
      const label = humanizeDirtyPath(path);
      items.push({ path, label });
      if (!seen.has(label)) {
        seen.add(label);
        labels.push(label);
      }
    }

    return { labels, items, affectsTotals, userEditCount: userEditCount || mutation.dirtyPaths.length };
  }, [mutation.dirtyPaths]);

  if (!mutation.dirty && !mutation.saveError) return null;

  const shownLabels = summary.labels.slice(0, 4).join(", ");
  const extraCount = Math.max(0, summary.labels.length - 4);
  const hasError = Boolean(mutation.saveError);

  const handleConfirmDiscard = async () => {
    setDiscarding(true);
    try {
      await onDiscard();
      setDiscardDialogOpen(false);
    } finally {
      setDiscarding(false);
    }
  };

  return (
    <>
      <div
        role="region"
        aria-label="Pending quotation changes"
        className={`sticky bottom-4 z-30 mr-16 ml-auto w-[calc(100%-4rem)] max-w-[1740px] rounded-[var(--rl-radius)] border px-4 py-3 shadow-lg backdrop-blur-md transition-all ${
          hasError
            ? "border-[var(--rl-red)]/40 bg-white/95"
            : "border-amber-300 bg-amber-50/95"
        }`}
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-start gap-2.5">
            <WarningCircle
              size={18}
              weight="fill"
              className={`mt-0.5 shrink-0 ${hasError ? "text-[var(--rl-red)]" : "text-amber-600"}`}
            />
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-xs font-bold text-[var(--rl-text-strong)]">
                <span>
                  {mutation.dirty
                    ? `${summary.userEditCount} unsaved change${summary.userEditCount === 1 ? "" : "s"} staged`
                    : "Save failed — changes retained"}
                </span>
                {summary.affectsTotals ? (
                  <span className="rounded-[var(--rl-radius-sm)] border border-amber-300/80 bg-white px-2 py-0.5 text-[11px] font-semibold text-amber-900">
                    Server recalculates exact RM total on Save &amp; Sync
                  </span>
                ) : null}
              </div>
              <p className="mt-0.5 truncate text-xs text-[var(--rl-text)]">
                {hasError
                  ? mutation.saveError
                  : `Modified: ${shownLabels}${extraCount > 0 ? ` +${extraCount} more` : ""}. Changes will sync to Ledger & Comparison when saved.`}
              </p>
              {!hasError && summary.items.length > 0 ? (
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  {summary.items.slice(0, 6).map((item) => (
                    <button
                      key={item.path}
                      type="button"
                      disabled={mutation.saving || discarding}
                      onClick={() => revertSinglePath(item.path)}
                      title={`Undo change to ${item.label}`}
                      className="inline-flex items-center gap-1 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-white px-2 py-0.5 text-[11px] font-semibold text-[#1b1717] hover:bg-amber-100/70 transition-colors cursor-pointer"
                    >
                      <span>{item.label}</span>
                      <X size={10} weight="bold" className="text-[#6e6e73]" />
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            {mutation.dirty ? (
              <Button
                type="button"
                variant="secondary"
                size="sm"
                icon={<ArrowCounterClockwise size={14} weight="bold" />}
                disabled={mutation.saving || discarding}
                onClick={() => setDiscardDialogOpen(true)}
              >
                Discard
              </Button>
            ) : null}
            <Button
              type="button"
              variant="primary"
              size="sm"
              loading={mutation.saving}
              icon={<FloppyDisk size={14} weight="bold" />}
              onClick={() => onSave()}
            >
              {mutation.saving ? "Saving & Syncing..." : hasError ? "Retry Save & Sync" : "Save & Sync"}
            </Button>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={discardDialogOpen}
        onOpenChange={setDiscardDialogOpen}
        title="Discard Unsaved Changes?"
        message="This will revert all staged edits on this screen back to the last saved quotation state."
        confirmLabel="Discard Changes"
        loading={discarding}
        onConfirm={handleConfirmDiscard}
      />
    </>
  );
}
