"use client";

import Link from "next/link";
import type { Route } from "next";
import { usePathname } from "next/navigation";

const items: Array<{ href: Route; label: string }> = [
  { href: "/settings/users" as Route, label: "Users" },
  { href: "/settings/system-checks" as Route, label: "System Checks" },
  { href: "/settings/storage" as Route, label: "Storage" },
  { href: "/settings/extraction/field-aliases" as Route, label: "Field Aliases" },
  { href: "/settings/extraction/vehicles" as Route, label: "Vehicles" },
  { href: "/settings/extraction/road-tax" as Route, label: "Road Tax" },
  { href: "/settings/extraction/companies" as Route, label: "Company Detection" },
];

export function SettingsNav() {
  const pathname = usePathname();
  return (
    <nav className="flex max-w-full gap-6 overflow-x-auto border-b border-[var(--rl-border)]" aria-label="Settings sections">
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
