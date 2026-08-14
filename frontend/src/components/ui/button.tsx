"use client";

import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { SpinnerGap } from "@phosphor-icons/react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const variantStyles: Record<ButtonVariant, string> = {
  primary:
    "bg-[var(--rl-black)] text-white border-[var(--rl-black)] hover:bg-[#2d2d2d] active:scale-[0.98]",
  secondary:
    "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] border-[var(--rl-border)] hover:bg-[var(--rl-bg)] active:scale-[0.98]",
  ghost:
    "bg-transparent text-[var(--rl-text)] border-transparent hover:bg-[var(--rl-bg)] active:scale-[0.98]",
  danger:
    "bg-[var(--rl-red)] text-white border-[var(--rl-red)] hover:bg-[var(--rl-red-hover)] active:scale-[0.98]",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
  icon?: ReactNode;
  size?: "sm" | "md";
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", loading, icon, size = "md", children, disabled, className = "", type = "button", ...props }, ref) => {
    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || loading}
        className={
          `inline-flex items-center justify-center font-semibold rounded-[var(--rl-radius-sm)] border transition-colors ${variantStyles[variant]}
          ${size === "sm" ? "min-h-[32px] gap-1.5 px-3 text-[13px]" : "min-h-[40px] gap-2 px-4 text-[14px]"}
          disabled:cursor-not-allowed disabled:opacity-50
          ${className}`
        }
        {...props}
      >
        {loading ? (
          <SpinnerGap aria-hidden="true" className="animate-spin" size={size === "sm" ? 14 : 16} />
        ) : (
          icon
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
