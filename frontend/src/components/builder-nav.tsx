"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/builder/companies", label: "Companies" },
  { href: "/builder/our-specials", label: "Our Specials" },
  { href: "/builder/templates", label: "Templates" },
] as const;

export function BuilderNav() {
  const pathname = usePathname();
  return (
    <nav className="flex gap-1 p-1 rounded-[var(--rl-radius)] bg-[var(--rl-bg)] w-fit" aria-label="Builder sections">
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
