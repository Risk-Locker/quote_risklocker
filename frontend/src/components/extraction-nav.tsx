"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";

const items: Array<{ href: Route; label: string }> = [
  { href: "/extraction/company-detection" as Route, label: "Company Detection" },
  { href: "/extraction/field-aliases" as Route, label: "Field Aliases" },
  { href: "/extraction/benefit-aliases" as Route, label: "Benefit Aliases" },
  { href: "/extraction/vehicles" as Route, label: "Vehicles" },
  { href: "/extraction/road-tax" as Route, label: "Road Tax" },
  { href: "/extraction/runner-fee" as Route, label: "Runner Fee" },
];

export function ExtractionNav() {
  const pathname = usePathname();
  return (
    <nav className="flex max-w-full gap-6 overflow-x-auto border-b border-[var(--rl-border)]" aria-label="Extraction and aliases sections">
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`border-b-2 px-0 py-3 text-[13px] font-semibold whitespace-nowrap
            ${active
                ? "border-[var(--rl-red)] text-[var(--rl-text-strong)]"
                : "border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
