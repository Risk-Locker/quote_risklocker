"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";

const items: Array<{ href: Route; label: string }> = [
  { href: "/builder/companies" as Route, label: "Companies" },
  { href: "/builder/our-specials" as Route, label: "Our Specials" },
  { href: "/builder/templates" as Route, label: "Templates" },
  { href: "/builder/assets" as Route, label: "Assets" },
];

export function BuilderNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-1 p-1 rounded-[var(--rl-radius)] bg-[var(--rl-bg)] w-fit max-w-full overflow-x-auto" aria-label="Builder sections">
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`rounded-[var(--rl-radius-sm)] px-3.5 py-2 text-[13px] font-semibold transition-all
            ${active
                ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] shadow-card"
                : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
