"use client";

import Link from "next/link";
import type { Route } from "next";
import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Upload, Wrench, Gear, Users, Bell, Trash, SignOut, SquaresFour } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAuth, clearAuthCache } from "@/lib/auth";
import { subscribe } from "@/lib/activity";
import { Button } from "@/components/ui/button";

const nav: Array<{ href: Route; label: string; icon: typeof Upload }> = [
  { href: "/upload", label: "Upload", icon: Upload },
  { href: "/sessions", label: "Sessions", icon: SquaresFour },
  { href: "/builder/templates", label: "Builder", icon: Wrench },
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
  const [requestsPending, setRequestsPending] = useState(0);
  const [clickPulse, setClickPulse] = useState(false);
  const [busyElapsed, setBusyElapsed] = useState(0);
  const firstRoute = useRef(true);
  const pulseTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => subscribe(setRequestsPending), []);

  const busy = requestsPending > 0 || clickPulse;

  useEffect(() => {
    if (!busy) {
      setBusyElapsed(0);
      return;
    }
    const started = Date.now();
    const timer = setInterval(() => setBusyElapsed(Math.round((Date.now() - started) / 100) / 10), 100);
    return () => clearInterval(timer);
  }, [busy]);

  const pulse = useCallback(() => {
    setClickPulse(true);
    if (pulseTimer.current) clearTimeout(pulseTimer.current);
    pulseTimer.current = setTimeout(() => setClickPulse(false), 900);
  }, []);

  useEffect(() => {
    if (firstRoute.current) {
      firstRoute.current = false;
      return;
    }
    pulse();
  }, [pathname, pulse]);

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
      <div
        aria-hidden="true"
        role="progressbar"
        aria-label="Loading"
        className={`fixed left-0 top-0 z-[60] h-[3px] bg-[var(--rl-red)] transition-all duration-500 ease-out
          ${busy ? "w-full opacity-100" : "w-0 opacity-0"}`}
      />
      <header className="sticky top-0 z-30 border-b border-[var(--rl-border)] bg-[var(--rl-surface)]/95 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1560px] items-center justify-between px-5 h-[56px]">
          <Link href="/upload" onClick={pulse} className="flex items-center gap-3 shrink-0">
            <img
              src="/assets/brand/logo-black.png"
              alt="Risklocker"
              className="h-8 w-auto"
            />
          </Link>
          <div className="flex items-center gap-3">
            {busy ? (
              <span
                role="status"
                className="inline-flex items-center gap-1.5 rounded-full border border-[var(--rl-red-light)] bg-[var(--rl-red-light)] px-2.5 py-1 text-[12px] font-bold text-[var(--rl-red)]"
              >
                <span className="size-2 animate-pulse rounded-full bg-[var(--rl-red)]" />
                Loading… {busyElapsed.toFixed(1)}s{requestsPending > 1 ? ` (${requestsPending} requests)` : ""}
              </span>
            ) : null}
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
          {nav.map((item) => {
            const Icon = item.icon;
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={pulse}
                className={`relative flex items-center gap-3 rounded-[var(--rl-radius-sm)] px-3 py-2.5 text-[14px] font-medium transition-all
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
