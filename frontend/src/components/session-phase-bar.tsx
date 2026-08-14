"use client";

import Link from "next/link";
import type { Route } from "next";
import { Check, LockKey } from "@phosphor-icons/react";

export type PhaseKey = "upload" | "extraction" | "preview";

const STEPS: Array<{ key: PhaseKey; label: string }> = [
  { key: "upload", label: "1. Upload" },
  { key: "extraction", label: "2. Check Values" },
  { key: "preview", label: "3. Preview & Generate" },
];

const STEP_HREFS: Record<PhaseKey, string> = {
  upload: "/upload",
  extraction: "check",
  preview: "preview",
};

type SessionPhaseBarProps = {
  sessionId: string;
  current: PhaseKey;
  hasVersion?: boolean;
  onStep?: (key: PhaseKey) => void;
};

export function SessionPhaseBar({ sessionId, current, hasVersion = false, onStep }: SessionPhaseBarProps) {
  const index = STEPS.findIndex((s) => s.key === current);
  return (
    <div className="flex flex-wrap items-center gap-1.5 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-1.5">
      {STEPS.map((step, i) => {
        const done = i < index || (step.key === "preview" && hasVersion);
        const active = step.key === current;
        const locked = step.key === "upload";
        return (
          <div key={step.key} className="flex items-center gap-1.5">
            {i > 0 ? <span className="text-[var(--rl-text-muted)]">→</span> : null}
            {locked ? (
              <span
                title="This session already has an upload. Start a new session for another quotation."
                className={`inline-flex items-center gap-1.5 rounded-[var(--rl-radius-sm)] px-3 py-1.5 text-[12px] font-semibold
                  ${active
                    ? "bg-[var(--rl-black)] text-white"
                    : "border border-[var(--rl-border)] bg-[var(--rl-bg)] text-[var(--rl-text-muted)] cursor-not-allowed"}`}
              >
                <LockKey size={13} weight="bold" />
                {step.label}
              </span>
            ) : (
              <Link
                href={step.key === "extraction" ? `/sessions/${sessionId}` : `/sessions/${sessionId}?step=preview` as Route}
                onClick={onStep ? (event) => {
                  event.preventDefault();
                  onStep(step.key);
                } : undefined}
                className={`inline-flex items-center gap-1.5 rounded-[var(--rl-radius-sm)] px-3 py-1.5 text-[12px] font-semibold transition-all
                  ${active
                    ? "bg-[var(--rl-black)] text-white shadow-card"
                    : done
                      ? "border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)]"
                      : "border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)]"}`}
              >
                {done ? <Check size={13} weight="bold" /> : null}
                {step.label}
              </Link>
            )}
          </div>
        );
      })}
    </div>
  );
}
