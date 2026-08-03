"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ReactNode } from "react";

type TabsProps = {
  value: string;
  onValueChange: (value: string) => void;
  items: Array<{ value: string; label: string; icon?: ReactNode }>;
};

export function Tabs({ value, onValueChange, items }: TabsProps) {
  return (
    <TabsPrimitive.Root value={value} onValueChange={onValueChange}>
      <TabsPrimitive.List className="flex gap-1 p-1 rounded-[var(--rl-radius)] bg-[var(--rl-bg)] w-fit">
        {items.map((item) => (
          <TabsPrimitive.Trigger
            key={item.value}
            value={item.value}
            className="inline-flex items-center gap-1.5 rounded-[var(--rl-radius-sm)] px-3.5 py-2 text-[13px] font-semibold transition-all
            text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]
            data-[state=active]:bg-[var(--rl-surface)] data-[state=active]:text-[var(--rl-text-strong)] data-[state=active]:shadow-card"
          >
            {item.icon}
            {item.label}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
    </TabsPrimitive.Root>
  );
}
