"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/settings/users", label: "Users" },
  { href: "/settings/system-checks", label: "System Checks" },
  { href: "/settings/storage", label: "Storage" },
  { href: "/settings/extraction/field-aliases", label: "Field Aliases" },
  { href: "/settings/extraction/vehicles", label: "Vehicles" },
  { href: "/settings/extraction/road-tax", label: "Road Tax" },
] as const;

export function SettingsNav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 p-1 rounded-[var(--rl-radius)] bg-[var(--rl-bg)] w-fit flex-wrap" aria-label="Settings sections">
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`rounded-[var(--rl-radius-sm)] px-3.5 py-2 text-[13px] font-semibold transition-all whitespace-nowrap
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
