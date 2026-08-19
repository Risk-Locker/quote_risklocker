"use client";

import Link from "next/link";
import type { Route } from "next";
import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Upload, Wrench, Gear, Users, Bell, Trash, SignOut, SquaresFour, FunnelSimple, Buildings } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAuth, clearAuthCache } from "@/lib/auth";
import { Button } from "@/components/ui/button";

const nav: Array<{ href: Route; label: string; icon: typeof Upload }> = [
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/sessions", label: "Sessions", icon: SquaresFour },
  { href: "/builder/templates", label: "Builder", icon: Wrench },
  { href: "/extraction/company-detection" as Route, label: "Extraction & Aliases", icon: FunnelSimple },
  { href: "/settings/system-checks", label: "Settings", icon: Gear },
  { href: "/client-records", label: "Records", icon: Users },
  { href: "/inbox", label: "Inbox", icon: Bell },
  { href: "/trash", label: "Trash", icon: Trash },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  const loadUnread = useCallback(async () => {
    try {
      const result = await api<{ unread_count: number }>("/notifications/unread-count");
      setUnreadCount(result.unread_count);
    } catch {
      setUnreadCount(0);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && user) {
      loadUnread();
    }
  }, [loadUnread, pathname, authLoading, user]);

  async function signOut() {
    setSigningOut(true);
    try {
      await api<void>("/auth/logout", { method: "POST" });
    } catch {
      // Session already invalid – still redirect.
    } finally {
      setSigningOut(false);
      clearAuthCache();
      router.replace("/login");
    }
  }

  if (authLoading || !user) {
    return (
      <div className="grid min-h-screen place-items-center bg-[var(--rl-bg)]">
        <p className="text-sm text-[var(--rl-text-muted)]">Checking session…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--rl-bg)]">
      <header className="sticky top-0 z-30 border-b border-[var(--rl-border)] bg-[var(--rl-surface)]/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1560px] items-center justify-between px-5 h-[56px]">
          <Link href="/upload" className="flex items-center gap-3 shrink-0">
            <img
              src="/assets/brand/logo-black.png"
              alt="Risklocker"
              className="h-8 w-auto"
            />
          </Link>
          <div className="flex items-center gap-3">
            <span className="text-[13px] font-medium text-[var(--rl-text-muted)] hidden sm:inline">
              {user?.email}
            </span>
            <Button
              variant="ghost"
              size="sm"
              loading={signingOut}
              icon={<SignOut weight="bold" size={16} />}
              onClick={signOut}
            >
              Sign out
            </Button>
          </div>
        </div>
      </header>
      <div className="mx-auto grid max-w-[1560px] grid-cols-[220px_minmax(0,1fr)] gap-6 px-5 py-6">
        <nav className="flex flex-col gap-1">
          {nav
            .filter((item) => {
              const isStaff = user?.role === "staff";
              if (isStaff) {
                return item.href === "/upload" || item.href === "/sessions";
              }
              return true;
            })
            .map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`relative flex items-center gap-3 rounded-[var(--rl-radius-sm)] px-3 py-2.5 text-[14px] font-medium transition-colors
                ${active
                    ? "bg-[var(--rl-black)] text-white shadow-card"
                    : "text-[var(--rl-text)] hover:bg-[var(--rl-surface)] hover:text-[var(--rl-text-strong)]"
                }`}
              >
                <Icon aria-hidden="true" size={18} weight={active ? "fill" : "regular"} />
                <span>{item.label}</span>
                {item.href === "/inbox" && unreadCount > 0 ? (
                  <span className="ml-auto flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[var(--rl-red)] px-1.5 text-[11px] font-bold text-white">
                    {unreadCount}
                  </span>
                ) : null}
              </Link>
            );
          })}
        </nav>
        <main className="min-w-0 animate-fade-in">{children}</main>
      </div>
    </div>
  );
}
