"use client";

import { ArrowsClockwise, UsersThree, WarningCircle, X } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { RealtimeEditor, RealtimeUpdateEvent } from "@/hooks/useRealtimeSync";

interface RealtimePresenceBannerProps {
  connected?: boolean;
  syncMode?: "live" | "polling" | "connecting";
  otherEditors: RealtimeEditor[];
  primaryEditor?: RealtimeEditor | null;
  isPrimaryEditor?: boolean;
  pendingUpdate: RealtimeUpdateEvent | null;
  onRefreshNow?: () => void;
  onDismissPending?: () => void;
  className?: string;
}

function formatEnteredTime(iso?: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return "";
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  } catch {
    return "";
  }
}

export function RealtimePresenceBanner({
  otherEditors,
  primaryEditor,
  isPrimaryEditor = true,
  pendingUpdate,
  onRefreshNow,
  onDismissPending,
  className = "",
}: RealtimePresenceBannerProps) {
  // Calm solo UI: render nothing when nobody else is here and no update is pending
  if (otherEditors.length === 0 && !pendingUpdate) {
    return null;
  }

  const otherNames = otherEditors
    .slice(0, 3)
    .map((ed) => ed.user_name || ed.user_email)
    .join(", ");
  const extraCount = otherEditors.length > 3 ? ` +${otherEditors.length - 3}` : "";

  const primaryName = primaryEditor ? primaryEditor.user_name || primaryEditor.user_email : "";
  const primaryEntered = formatEnteredTime(primaryEditor?.entered_at || primaryEditor?.updated_at);

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      {otherEditors.length > 0 && !isPrimaryEditor && primaryEditor ? (
        <div
          role="status"
          className="inline-flex items-center gap-2 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-950"
        >
          <WarningCircle size={14} weight="fill" className="text-amber-600 shrink-0" />
          <span>
            {primaryName} is currently working in this workspace
            {primaryEntered ? ` (entered ${primaryEntered})` : ""} — they have edit priority. Consider letting them finish to avoid overwriting changes.
          </span>
        </div>
      ) : otherEditors.length > 0 ? (
        <Badge variant="default" className="gap-1.5 border border-[var(--rl-border)]">
          <UsersThree size={13} weight="bold" className="text-sky-600" />
          <span>
            {otherNames}
            {extraCount} {otherEditors.length === 1 ? "is" : "are"} also viewing this workspace
          </span>
        </Badge>
      ) : null}

      {pendingUpdate && (
        <div className="inline-flex items-center gap-2 rounded-[var(--rl-radius-sm)] border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-900">
          <span>
            Updated by {pendingUpdate.actor_name || pendingUpdate.actor_email || "teammate"}
            {pendingUpdate.summary ? ` — ${pendingUpdate.summary}` : ""}
          </span>
          {onRefreshNow && (
            <Button size="sm" variant="primary" onClick={onRefreshNow} className="h-6 px-2 text-[11px]">
              <ArrowsClockwise size={12} weight="bold" />
              <span>Refresh now</span>
            </Button>
          )}
          {onDismissPending && (
            <button
              type="button"
              onClick={onDismissPending}
              className="rounded p-0.5 text-amber-700 hover:bg-amber-200/70 cursor-pointer"
              aria-label="Dismiss update banner"
            >
              <X size={12} weight="bold" />
            </button>
          )}
        </div>
      )}
    </div>
  );
}
