"use client";

import { useId } from "react";
import { Users, CircleNotch, Lightning, HourglassHigh } from "@phosphor-icons/react";

export interface QueueProgressBannerProps {
  currentProcessingIndex: number;
  totalItems: number;
  queuePosition?: number;
  otherUsersCount?: number;
  activePhase?: string;
  isFairShareActive?: boolean;
}

export function QueueProgressBanner({
  currentProcessingIndex,
  totalItems,
  queuePosition,
  otherUsersCount = 0,
  activePhase = "extracting",
  isFairShareActive = true,
}: QueueProgressBannerProps) {
  const isMultiUser = otherUsersCount > 0;
  const posText = queuePosition && queuePosition > 0 ? `Position ${queuePosition} in queue` : "Processing next";
  const userText = isMultiUser
    ? `${otherUsersCount} other staff member${otherUsersCount > 1 ? "s" : ""} currently processing`
    : "Dedicated slot assigned";

  return (
    <div className="rounded-[var(--rl-radius)] border border-[#e5e5ea] bg-[#f5f5f7] p-3.5 shadow-2xs transition-all">
      <div className="flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2.5">
          <span className="relative flex size-6 shrink-0 items-center justify-center rounded-lg bg-[#1b1717] text-white">
            <CircleNotch size={14} weight="bold" className="animate-spin text-amber-400" />
          </span>
          <div>
            <div className="flex items-center gap-1.5 font-bold text-[#1b1717]">
              <span>
                Processing item {Math.min(currentProcessingIndex, totalItems)} of {totalItems}
              </span>
              <span className="text-[10px] text-[#8e8e93] font-normal">•</span>
              <span className="text-[11px] font-mono text-[#6e6e73] capitalize">
                {activePhase.replace("_", " ")}
              </span>
            </div>
            <p className="text-[11px] text-[#6e6e73]">
              {posText}. {userText}.
            </p>
          </div>
        </div>

        {isFairShareActive && (
          <div className="flex items-center gap-2">
            {isMultiUser && (
              <span className="flex items-center gap-1 rounded-md border border-[#e5e5ea] bg-white px-2 py-0.5 text-[10px] font-semibold text-[#1b1717]">
                <Users size={12} weight="bold" className="text-neutral-500" />
                <span>Fair-Share Interleaved</span>
              </span>
            )}
            <span className="flex items-center gap-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-900">
              <Lightning size={12} weight="fill" className="text-amber-500" />
              <span>Safe 12 RPM Sharded</span>
            </span>
          </div>
        )}
      </div>

      {/* Micro-Progress Bar */}
      <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-neutral-200/80">
        <div
          className="h-full bg-[#1b1717] transition-all duration-300"
          style={{
            width: `${Math.max(5, Math.min(100, (currentProcessingIndex / Math.max(1, totalItems)) * 100))}%`,
          }}
        />
      </div>
    </div>
  );
}

