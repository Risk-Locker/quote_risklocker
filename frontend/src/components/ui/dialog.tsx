"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "@phosphor-icons/react";
import type { ReactNode } from "react";
import { Button } from "./button";

type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  onConfirm?: () => void;
  confirmLabel?: string;
  confirmVariant?: "primary" | "danger";
  loading?: boolean;
};

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  onConfirm,
  confirmLabel = "Confirm",
  confirmVariant = "primary",
  loading = false,
}: DialogProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/40 animate-fade-in" />
        <DialogPrimitive.Content
          className="fixed left-1/2 top-1/2 z-50 w-[calc(100vw-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-6 shadow-lift animate-fade-in overflow-hidden"
        >
          <DialogPrimitive.Close asChild>
            <button
              type="button"
              className="absolute right-4 top-4 rounded p-1 text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)] transition-colors z-10"
              aria-label="Close"
            >
              <X size={16} weight="bold" />
            </button>
          </DialogPrimitive.Close>
          <DialogPrimitive.Title className="text-[18px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)] pr-8 break-words [overflow-wrap:anywhere]">
            {title}
          </DialogPrimitive.Title>
          {description ? (
            <DialogPrimitive.Description className="mt-2 text-[14px] text-[var(--rl-text)] break-words [overflow-wrap:anywhere]">{description}</DialogPrimitive.Description>
          ) : null}
          {children ? <div className="mt-4">{children}</div> : null}
          {onConfirm ? (
            <div className="mt-5 flex gap-2 justify-end">
              <DialogPrimitive.Close asChild>
                <Button variant="secondary" size="sm">Cancel</Button>
              </DialogPrimitive.Close>
              <Button variant={confirmVariant} size="sm" loading={loading} onClick={onConfirm}>
                {confirmLabel}
              </Button>
            </div>
          ) : null}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
