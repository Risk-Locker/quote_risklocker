"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/builder/companies", label: "Companies" },
  { href: "/builder/our-specials", label: "Our Specials" },
  { href: "/builder/templates", label: "Templates" }
] as const;

export function BuilderNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-2" aria-label="Builder sections">
      {items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`rounded-md border px-3 py-2 text-sm font-bold ${active ? "border-rl-black bg-rl-black text-rl-inverse" : "border-rl-line text-rl-textStrong hover:bg-rl-soft"}`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
