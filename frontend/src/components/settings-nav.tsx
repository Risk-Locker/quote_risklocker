"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/settings/users", label: "Users" },
  { href: "/settings/system-checks", label: "System Checks" },
  { href: "/settings/storage", label: "Storage" },
  { href: "/settings/extraction/field-aliases", label: "Field Aliases" },
  { href: "/settings/extraction/vehicles", label: "Vehicles" },
  { href: "/settings/extraction/road-tax", label: "Road Tax" }
] as const;

export function SettingsNav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-wrap gap-2" aria-label="Settings sections">
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
