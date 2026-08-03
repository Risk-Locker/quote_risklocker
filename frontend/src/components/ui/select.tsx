"use client";

import { forwardRef } from "react";
import type { SelectHTMLAttributes } from "react";

type SelectProps = SelectHTMLAttributes<HTMLSelectElement> & {
  error?: boolean;
};

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ error, className = "", children, ...props }, ref) => {
    return (
      <select
        ref={ref}
        className={
          `min-h-[40px] w-full rounded-[var(--rl-radius-sm)] border px-3 py-2 text-[14px] text-[var(--rl-text-strong)]
          bg-[var(--rl-surface)] transition-colors cursor-pointer
          ${error ? "border-[var(--rl-red)]" : "border-[var(--rl-border)] hover:border-[var(--rl-text-muted)] focus:border-[var(--rl-black)] focus:outline-none"}
          ${className}`
        }
        {...props}
      >
        {children}
      </select>
    );
  }
);

Select.displayName = "Select";
