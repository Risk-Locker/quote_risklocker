"use client";

import { ArrowsClockwise, Broadcast, UsersThree, X } from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { RealtimeEditor, RealtimeUpdateEvent } from "@/hooks/useRealtimeSync";

interface RealtimePresenceBannerProps {
  connected: boolean;
  otherEditors: RealtimeEditor[];
  pendingUpdate: RealtimeUpdateEvent | null;
  onRefreshNow?: () => void;
  onDismissPending?: () => void;
  className?: string;
}

export function RealtimePresenceBanner({
  connected,
  otherEditors,
  pendingUpdate,
  onRefreshNow,
  onDismissPending,
  className = "",
}: RealtimePresenceBannerProps) {
  const editorText = otherEditors
    .slice(0, 3)
    .map((ed) => {
      const label = ed.user_email || ed.user_name;
      return ed.field ? `${label} (${ed.field})` : label;
    })
    .join(", ");

  const extraCount = otherEditors.length > 3 ? ` +${otherEditors.length - 3}` : "";

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      <Badge variant={connected ? "success" : "info"} className="gap-1.5 font-medium">
        <span
          className={`inline-block size-2 rounded-full ${
            connected ? "bg-emerald-500 animate-pulse" : "bg-neutral-400"
          }`}
        />
        <Broadcast size={13} weight="bold" />
        <span>{connected ? "Live sync" : "Syncing..."}</span>
      </Badge>

      {otherEditors.length > 0 && (
        <Badge variant="default" className="gap-1.5 border border-[var(--rl-border)]">
          <UsersThree size={13} weight="bold" className="text-sky-600" />
          <span>
            Editing now: {editorText}
            {extraCount}
          </span>
        </Badge>
      )}

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
