"use client";

type Status = "Ready" | "Check Needed" | "Cannot Read" | "Generated" | "Deleted" | "Preparing" | "Uploaded" | string;

const styles: Record<string, string> = {
  Ready: "bg-[var(--rl-success-light)] text-[var(--rl-success)]",
  "Check Needed": "bg-[var(--rl-warning-light)] text-[var(--rl-warning)]",
  "Cannot Read": "bg-[var(--rl-red-light)] text-[var(--rl-red)]",
  Generated: "bg-[var(--rl-black)]/8 text-[var(--rl-text-strong)]",
  Deleted: "bg-[var(--rl-black)]/5 text-[var(--rl-text-muted)]",
  Preparing: "bg-[var(--rl-black)]/6 text-[var(--rl-text-muted)]",
  Uploaded: "bg-[var(--rl-black)]/5 text-[var(--rl-text-muted)]",
};

export function StatusBadge({ status }: { status: Status }) {
  return (
    <span className={`inline-flex min-h-[26px] items-center rounded-[var(--rl-radius-sm)] px-2.5 py-0.5 text-[12px] font-semibold leading-none ${styles[status] || styles.Uploaded}`}>
      {status}
    </span>
  );
}
