"use client";

import { forwardRef } from "react";
import type { TextareaHTMLAttributes } from "react";

type TextareaProps = TextareaHTMLAttributes<HTMLTextAreaElement> & {
  error?: boolean;
};

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ error, className = "", ...props }, ref) => {
    return (
      <textarea
        ref={ref}
        className={
          `min-h-[80px] w-full rounded-[var(--rl-radius-sm)] border px-3 py-2 text-[14px] text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)]
          bg-[var(--rl-surface)] resize-y transition-colors
          ${error ? "border-[var(--rl-red)]" : "border-[var(--rl-border)] hover:border-[var(--rl-text-muted)] focus:border-[var(--rl-black)] focus:outline-none"}
          ${className}`
        }
        {...props}
      />
    );
  }
);

Textarea.displayName = "Textarea";
