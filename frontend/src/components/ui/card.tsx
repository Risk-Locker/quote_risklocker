"use client";

import type { HTMLAttributes, ReactNode } from "react";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  hover?: boolean;
};

export function Card({ children, className = "", hover = false, ...props }: CardProps) {
  return (
    <div
      className={`rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-card transition-all
      ${hover ? "hover:shadow-lift hover:-translate-y-px" : ""}
      ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
