"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";

const items: Array<{ href: Route; label: string }> = [
  { href: "/builder/templates" as Route, label: "Templates" },
  { href: "/builder/companies" as Route, label: "Insurance Companies" },
  { href: "/builder/benefits" as Route, label: "Benefits" },
  { href: "/builder/global-benefits" as Route, label: "Global Benefits" },
  { href: "/builder/assets" as Route, label: "Asset Library" },
];

export function BuilderNav() {
  const pathname = usePathname();
  return (
    <nav className="flex max-w-full gap-6 overflow-x-auto border-b border-[var(--rl-border)]" aria-label="Builder sections">
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`-mb-px border-b-2 px-0.5 pb-3 pt-1 text-[13px] font-semibold transition-colors
            ${active
                ? "border-[var(--rl-red)] text-[var(--rl-text-strong)]"
                : "border-transparent text-[var(--rl-text-muted)] hover:border-[var(--rl-border-strong)] hover:text-[var(--rl-text-strong)]"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
