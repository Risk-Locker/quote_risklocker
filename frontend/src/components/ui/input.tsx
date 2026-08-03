"use client";

import { forwardRef } from "react";
import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  error?: boolean;
};

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ error, className = "", ...props }, ref) => {
    return (
      <input
        ref={ref}
        className={
          `min-h-[40px] w-full rounded-[var(--rl-radius-sm)] border px-3 py-2 text-[14px] text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)]
          bg-[var(--rl-surface)] transition-colors
          ${error ? "border-[var(--rl-red)]" : "border-[var(--rl-border)] hover:border-[var(--rl-text-muted)] focus:border-[var(--rl-black)] focus:outline-none"}
          ${className}`
        }
        {...props}
      />
    );
  }
);

Input.displayName = "Input";
