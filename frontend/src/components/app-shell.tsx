"use client";

import Link from "next/link";
import type { Route } from "next";
import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { FileClock, Inbox, LogOut, Settings, Upload, Rows3, Trash2, PanelLeftClose, PanelLeftOpen, Users } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const nav: Array<{ href: Route; label: string; icon: typeof Upload; badge?: boolean }> = [
  { href: "/upload", label: "Upload Quotation PDFs", icon: Upload },
  { href: "/history", label: "History", icon: FileClock },
  { href: "/builder/templates", label: "Builder", icon: Settings },
  { href: "/settings/system-checks", label: "Settings", icon: Settings },
  { href: "/client-records", label: "Client Records", icon: Users },
  { href: "/inbox", label: "Inbox", icon: Inbox, badge: true },
  { href: "/trash", label: "Trash", icon: Trash2 },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [collapsed, setCollapsed] = useState(true);
  const [signingOut, setSigningOut] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (!authLoading && user === null) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    setCollapsed(localStorage.getItem("rl-sidebar-collapsed") !== "false");
  }, []);

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

  function toggleSidebar() {
    setCollapsed((current) => {
      const next = !current;
      localStorage.setItem("rl-sidebar-collapsed", String(next));
      return next;
    });
  }

  async function signOut() {
    setSigningOut(true);
    try {
      await api<void>("/auth/logout", { method: "POST" });
    } catch {
      // If the session was already invalid, the cookie will still be cleared by the backend.
      // We still want the user back on the login page.
    } finally {
      setSigningOut(false);
      router.replace("/login");
    }
  }

  if (authLoading || user === null) {
    return (
      <div className="grid min-h-screen place-items-center bg-rl-soft">
        <p className="text-sm text-rl-text">Checking session…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-rl-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-4">
          <Link href="/upload" className="flex items-center gap-3 font-bold text-rl-textStrong">
            <Rows3 aria-hidden="true" size={22} />
            <span>Risklocker Quotation Converter</span>
          </Link>
          <button
            className="rl-button rl-button-secondary"
            onClick={signOut}
            disabled={signingOut}
            type="button"
          >
            <LogOut aria-hidden="true" size={18} />
            {signingOut ? "Signing out" : "Sign out"}
          </button>
        </div>
      </header>
      <div className={`mx-auto grid max-w-[1560px] grid-cols-1 gap-5 px-5 py-5 ${collapsed ? "lg:grid-cols-[72px_1fr]" : "lg:grid-cols-[230px_1fr]"}`}>
        <nav className="lg:border-r lg:border-rl-line lg:pr-3">
          <button
            className="rl-button rl-button-secondary mb-3 hidden w-full lg:inline-flex"
            type="button"
            onClick={toggleSidebar}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <PanelLeftOpen aria-hidden="true" size={18} /> : <PanelLeftClose aria-hidden="true" size={18} />}
            <span className={collapsed ? "sr-only" : ""}>{collapsed ? "Expand" : "Collapse"}</span>
          </button>
          <div className="grid gap-2">
            {nav.map((item) => {
              const Icon = item.icon;
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  title={collapsed ? item.label : undefined}
                  className={`relative flex min-h-11 items-center gap-3 rounded-md px-3 py-2 font-bold ${
                    active ? "bg-rl-black text-rl-inverse" : "text-rl-textStrong hover:bg-rl-soft"
                  }`}
                >
                  <Icon aria-hidden="true" size={18} />
                  <span className={collapsed ? "lg:sr-only" : ""}>{item.label}</span>
                  {item.badge && unreadCount > 0 ? (
                    <span
                      className={`absolute right-2 top-1/2 flex h-5 min-w-[20px] -translate-y-1/2 items-center justify-center rounded-full bg-rl-red px-1 text-[11px] font-bold leading-tight text-white ${collapsed ? "lg:right-0.5 lg:top-0.5 lg:-translate-y-0" : ""}`}
                      aria-label={`${unreadCount} unread notification${unreadCount === 1 ? "" : "s"}`}
                    >
                      {unreadCount}
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </div>
        </nav>
        <main>{children}</main>
      </div>
    </div>
  );
}
