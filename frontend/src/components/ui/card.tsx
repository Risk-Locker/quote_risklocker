"use client";

import type { ReactNode } from "react";

type CardProps = {
  children: ReactNode;
  className?: string;
  hover?: boolean;
};

export function Card({ children, className = "", hover = false }: CardProps) {
  return (
    <div
      className={`rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-card transition-all
      ${hover ? "hover:shadow-lift hover:-translate-y-px" : ""}
      ${className}`}
    >
      {children}
    </div>
  );
}
