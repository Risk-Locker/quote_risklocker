"use client";

type BadgeProps = {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "info";
  className?: string;
};

const variantStyles: Record<string, string> = {
  default: "bg-[var(--rl-black)]/8 text-[var(--rl-text-strong)]",
  success: "bg-[var(--rl-success-light)] text-[var(--rl-success)]",
  warning: "bg-[var(--rl-warning-light)] text-[var(--rl-warning)]",
  danger: "bg-[var(--rl-red-light)] text-[var(--rl-red)]",
  info: "bg-[var(--rl-black)]/6 text-[var(--rl-text-muted)]",
};

export function Badge({ children, variant = "default", className = "" }: BadgeProps) {
  return (
    <span
      className={`inline-flex min-h-[26px] items-center rounded-[var(--rl-radius-sm)] px-2.5 py-0.5 text-[12px] font-semibold leading-none
      ${variantStyles[variant]} ${className}`}
    >
      {children}
    </span>
  );
}
