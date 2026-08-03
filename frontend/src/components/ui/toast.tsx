"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { CheckCircle, Warning, XCircle, Info, X } from "@phosphor-icons/react";
import { AnimatePresence, motion } from "framer-motion";

type ToastVariant = "success" | "error" | "warning" | "info";

type ToastItem = {
  id: string;
  message: string;
  variant: ToastVariant;
};

type ToastContextType = {
  toast: (message: string, variant?: ToastVariant) => void;
};

const ToastContext = createContext<ToastContextType | null>(null);

const icons: Record<ToastVariant, typeof CheckCircle> = {
  success: CheckCircle,
  error: XCircle,
  warning: Warning,
  info: Info,
};

const colorStyles: Record<ToastVariant, string> = {
  success: "border-[var(--rl-success)] bg-[var(--rl-success-light)] text-[var(--rl-success)]",
  error: "border-[var(--rl-red)] bg-[var(--rl-red-light)] text-[var(--rl-red)]",
  warning: "border-[var(--rl-warning)] bg-[var(--rl-warning-light)] text-[var(--rl-warning)]",
  info: "border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)]",
};

export function Toaster({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const counterRef = useRef(0);

  const toast = useCallback((message: string, variant: ToastVariant = "info") => {
    const id = String(++counterRef.current);
    setToasts((prev) => [...prev.slice(-4), { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const remove = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed right-5 top-5 z-50 flex flex-col-reverse gap-2 pointer-events-none">
        <AnimatePresence>
          {toasts.map((t) => {
            const Icon = icons[t.variant];
            return (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, x: 20, scale: 0.96 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 20, scale: 0.96 }}
                transition={{ duration: 0.25, ease: [0.25, 0.1, 0.25, 1] }}
                className={`pointer-events-auto flex items-center gap-2.5 rounded-[var(--rl-radius-sm)] border px-4 py-3 text-[14px] font-semibold shadow-lift ${colorStyles[t.variant]}`}
              >
                <Icon aria-hidden="true" size={18} weight="fill" />
                <span className="leading-tight">{t.message}</span>
                <button
                  type="button"
                  onClick={() => remove(t.id)}
                  className="ml-2 rounded p-0.5 opacity-60 hover:opacity-100 transition-opacity"
                  aria-label="Dismiss"
                >
                  <X size={14} weight="bold" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within <Toaster>");
  return ctx;
}
