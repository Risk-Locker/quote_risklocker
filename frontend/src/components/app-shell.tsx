"use client";

import Link from "next/link";
import type { Route } from "next";
import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Lock,
  Upload,
  Wrench,
  Gear,
  Users,
  Bell,
  Trash,
  SignOut,
  SquaresFour,
  FunnelSimple,
  Brain,
  SidebarSimple,
  List,
  X,
  ChartLineUp,
  CalendarBlank,
  Columns,
  ClockCounterClockwise,
} from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAuth, clearAuthCache } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { GlobalAiCopilot } from "@/components/global-ai-copilot";
import { GeminiHeaderMeter } from "@/components/gemini-header-meter";

interface NavItem {
  href: Route;
  label: string;
  icon: typeof Upload;
  staffRestricted?: boolean;
}

interface NavSection {
  title?: string;
  staffRestricted?: boolean;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: "OPERATIONS",
    items: [
      { href: "/ledger" as Route, label: "Motor Renewal Ledger", icon: CalendarBlank },
      { href: "/sessions" as Route, label: "Sessions", icon: ClockCounterClockwise },
      { href: "/upload/marketing-comparison" as Route, label: "Upload & Intake", icon: Upload },
      { href: "/client-records" as Route, label: "Client Records", icon: Users },
    ],
  },
  {
    title: "STUDIO & CONFIG",
    staffRestricted: true,
    items: [
      { href: "/builder/templates/quotation-templates" as Route, label: "Builder", icon: Wrench, staffRestricted: true },
      { href: "/extraction/company-detection" as Route, label: "Extraction & Aliases", icon: FunnelSimple, staffRestricted: true },
      { href: "/settings/system-checks", label: "Settings", icon: Gear, staffRestricted: true },
    ],
  },
  {
    title: "SYSTEM",
    staffRestricted: true,
    items: [
      { href: "/inbox", label: "Inbox", icon: Bell, staffRestricted: true },
      { href: "/trash", label: "Trash", icon: Trash, staffRestricted: true },
    ],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [signingOut, setSigningOut] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem("rl_sidebar_collapsed");
      if (stored !== null) {
        setIsCollapsed(stored === "true");
      }
    } catch {
      // Best effort
    }
  }, []);

  const toggleCollapse = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("rl_sidebar_collapsed", String(next));
      } catch {
        // Best effort
      }
      return next;
    });
  };

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  // Client-side route guard: Staff users cannot view admin/builder/settings/extraction/system pages
  const isStaff = user?.role === "staff";
  const isRestrictedForStaff =
    Boolean(isStaff) &&
    (pathname.startsWith("/builder") ||
      pathname.startsWith("/extraction") ||
      pathname.startsWith("/settings") ||
      pathname.startsWith("/admin") ||
      pathname.startsWith("/ai-context") ||
      pathname === "/inbox" ||
      pathname === "/trash");

  useEffect(() => {
    if (!authLoading && user && isRestrictedForStaff) {
      router.replace("/upload/marketing-comparison");
    }
  }, [authLoading, user, isRestrictedForStaff, router]);

  // Close mobile drawer on route navigation
  useEffect(() => {
    setMobileNavOpen(false);
  }, [pathname]);

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

  if (isRestrictedForStaff) {
    return (
      <div className="grid min-h-screen place-items-center bg-[var(--rl-bg)]">
        <div className="text-center p-6 bg-white border border-[var(--rl-border)] rounded-lg shadow-sm max-w-sm">
          <Lock size={28} className="mx-auto text-[var(--rl-text-muted)] mb-2" />
          <h2 className="text-sm font-semibold text-[var(--rl-text-strong)]">Access Restricted</h2>
          <p className="text-xs text-[var(--rl-text-muted)] mt-1">This workspace is restricted to administrators and engineering staff.</p>
        </div>
      </div>
    );
  }

  // All nav sections are kept so staff can faintly see them in a disabled state ("unclickable and slightly hidden")
  const filteredSections = navSections;

  return (
    <div className="min-h-screen bg-[var(--rl-bg)]">
      {/* Header */}
      <header className="sticky top-0 z-40 w-full border-b border-[var(--rl-border)] bg-[var(--rl-surface)]/95 backdrop-blur-sm">
        <div className="mx-auto flex w-full items-center justify-between px-4 sm:px-5 h-[56px]">
          <div className="flex items-center gap-3">
            {/* Mobile menu hamburger button */}
            <button
              type="button"
              onClick={() => setMobileNavOpen(true)}
              aria-label="Open mobile navigation"
              className="grid size-9 place-items-center rounded-[var(--rl-radius-sm)] text-[var(--rl-text-muted)] hover:bg-black/5 hover:text-[var(--rl-text-strong)] transition-colors md:hidden cursor-pointer"
            >
              <List size={20} weight="bold" />
            </button>

            <Link href="/upload" className="flex items-center gap-2.5">
              <img
                src="/assets/brand/logo-black.png"
                alt="Risklocker"
                className="h-6 w-auto"
              />
            </Link>

            {/* Sidebar toggle button (desktop) */}
            <button
              type="button"
              onClick={toggleCollapse}
              aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="hidden md:grid size-8 place-items-center rounded-[var(--rl-radius-sm)] text-[var(--rl-text-muted)] hover:bg-black/5 hover:text-[var(--rl-text-strong)] transition-colors ml-1 cursor-pointer"
            >
              <SidebarSimple size={18} weight={isCollapsed ? "fill" : "bold"} />
            </button>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            {isStaff ? (
              <div className="opacity-25 pointer-events-none select-none grayscale cursor-not-allowed hidden sm:block" title="Admin only">
                <GeminiHeaderMeter />
              </div>
            ) : (
              <GeminiHeaderMeter />
            )}
            <span className="text-[13px] font-medium text-[var(--rl-text-strong)] hidden sm:inline">
              {user?.name || user?.email}
            </span>
            <Button
              variant="ghost"
              size="sm"
              loading={signingOut}
              icon={<SignOut weight="bold" size={16} />}
              onClick={signOut}
            >
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </div>
        </div>
      </header>

      {/* Mobile slide-over drawer overlay & sheet */}
      {mobileNavOpen && (
        <div className="fixed inset-0 z-50 md:hidden animate-fade-in">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/40 backdrop-blur-xs"
            onClick={() => setMobileNavOpen(false)}
            aria-hidden="true"
          />

          {/* Drawer panel */}
          <div className="fixed inset-y-0 left-0 w-[270px] max-w-[85vw] bg-white border-r border-[var(--rl-border)] p-4 flex flex-col justify-between shadow-lift z-50 overflow-y-auto">
            <div>
              <div className="flex items-center justify-between pb-4 border-b border-[var(--rl-border)] mb-4">
                <img
                  src="/assets/brand/logo-black.png"
                  alt="Risklocker"
                  className="h-7 w-auto"
                />
                <button
                  type="button"
                  onClick={() => setMobileNavOpen(false)}
                  aria-label="Close navigation"
                  className="grid size-8 place-items-center rounded-[var(--rl-radius-sm)] text-[var(--rl-text-muted)] hover:bg-black/5"
                >
                  <X size={18} weight="bold" />
                </button>
              </div>

              <nav className="flex flex-col gap-4">
                {filteredSections.map((section, sIdx) => {
                  const isSectionLocked = isStaff && section.staffRestricted;
                  return (
                    <div
                      key={sIdx}
                      className={`space-y-1 ${
                        isSectionLocked ? "opacity-25 pointer-events-none select-none grayscale cursor-not-allowed" : ""
                      }`}
                    >
                      {section.title && (
                        <div className="flex items-center justify-between px-3">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] block select-none">
                            {section.title}
                          </span>
                          {isSectionLocked && (
                            <span className="inline-flex items-center gap-1 text-[9px] font-semibold text-[var(--rl-text-muted)]">
                              <Lock size={10} weight="bold" /> Admin
                            </span>
                          )}
                        </div>
                      )}
                      {section.items.map((item) => {
                        const Icon = item.icon;
                        const isBuilder = item.href.startsWith("/builder");
                        const isUpload = item.href.startsWith("/upload");
                        const active = !isSectionLocked && (isBuilder
                          ? pathname.startsWith("/builder")
                          : isUpload
                          ? pathname.startsWith("/upload")
                          : pathname === item.href || pathname.startsWith(`${item.href}/`));
                        return (
                          <Link
                            key={item.href}
                            href={isSectionLocked ? "#" : item.href}
                            tabIndex={isSectionLocked ? -1 : undefined}
                            onClick={() => !isSectionLocked && setMobileNavOpen(false)}
                            className={`relative flex items-center gap-3 rounded-[var(--rl-radius-sm)] px-3 py-2 text-[13px] font-medium transition-colors ${
                              active
                                ? "bg-[var(--rl-black)] text-white shadow-card"
                                : "text-[var(--rl-text)] hover:bg-[var(--rl-bg)] hover:text-[var(--rl-text-strong)]"
                            }`}
                          >
                            <Icon aria-hidden="true" size={17} weight={active ? "fill" : "regular"} />
                            <span>{item.label}</span>
                            {isSectionLocked && (
                              <Lock size={12} weight="bold" className="ml-auto text-[var(--rl-text-muted)]" />
                            )}
                            {!isSectionLocked && item.href === "/inbox" && unreadCount > 0 ? (
                              <span className="ml-auto flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[var(--rl-red)] px-1.5 text-[11px] font-bold text-white">
                                {unreadCount}
                              </span>
                            ) : null}
                          </Link>
                        );
                      })}
                    </div>
                  );
                })}
              </nav>
            </div>

            <div className="pt-4 border-t border-[var(--rl-border)] flex items-center justify-between text-xs text-[var(--rl-text-muted)]">
              <span className="truncate max-w-[150px]">{user?.email}</span>
              <Button
                variant="ghost"
                size="sm"
                icon={<SignOut weight="bold" size={14} />}
                onClick={signOut}
              >
                Sign out
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Main Grid Container */}
      <div
        className={`mx-auto grid w-full gap-4 sm:gap-6 px-3 sm:px-5 py-4 sm:py-6 transition-[grid-template-columns] duration-200 ${
          isCollapsed
            ? "grid-cols-1 md:grid-cols-[64px_minmax(0,1fr)]"
            : "grid-cols-1 md:grid-cols-[220px_minmax(0,1fr)]"
        }`}
      >
        {/* Desktop Sidebar */}
        <aside className="hidden md:block">
          <nav className="flex flex-col gap-3 sticky top-[80px]">
            {filteredSections.map((section, sIdx) => {
              const isSectionLocked = isStaff && section.staffRestricted;
              return (
                <div
                  key={sIdx}
                  className={`space-y-1 ${
                    isSectionLocked ? "opacity-25 pointer-events-none select-none grayscale cursor-not-allowed" : ""
                  }`}
                >
                  {!isCollapsed && section.title && (
                    <div className="flex items-center justify-between px-3 pt-1 pb-0.5">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] block select-none">
                        {section.title}
                      </span>
                      {isSectionLocked && (
                        <span className="inline-flex items-center gap-1 text-[9px] font-semibold text-[var(--rl-text-muted)]">
                          <Lock size={10} weight="bold" /> Admin
                        </span>
                      )}
                    </div>
                  )}
                  {isCollapsed && sIdx > 0 && (
                    <div className="my-1.5 mx-2 border-t border-[var(--rl-border)]" />
                  )}
                  {section.items.map((item) => {
                    const Icon = item.icon;
                    const isBuilder = item.href.startsWith("/builder");
                    const isUpload = item.href.startsWith("/upload");
                    const active = !isSectionLocked && (isBuilder
                      ? pathname.startsWith("/builder")
                      : isUpload
                      ? pathname.startsWith("/upload")
                      : pathname === item.href || pathname.startsWith(`${item.href}/`));

                    const navLink = (
                      <Link
                        key={item.href}
                        href={isSectionLocked ? "#" : item.href}
                        tabIndex={isSectionLocked ? -1 : undefined}
                        className={`relative flex items-center rounded-[var(--rl-radius-sm)] transition-all ${
                          isCollapsed
                            ? "justify-center px-2 py-2"
                            : "gap-3 px-3 py-2 text-[13px] font-medium"
                        } ${
                          active
                            ? "bg-[var(--rl-black)] text-white shadow-card"
                            : "text-[var(--rl-text)] hover:bg-[var(--rl-surface)] hover:text-[var(--rl-text-strong)]"
                        }`}
                      >
                        <Icon aria-hidden="true" size={18} weight={active ? "fill" : "regular"} className="shrink-0" />
                        {!isCollapsed ? (
                          <>
                            <span className="truncate">{item.label}</span>
                            {isSectionLocked ? (
                              <Lock size={12} weight="bold" className="ml-auto text-[var(--rl-text-muted)]" />
                            ) : item.href === "/inbox" && unreadCount > 0 ? (
                              <span className="ml-auto flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[var(--rl-red)] px-1.5 text-[11px] font-bold text-white">
                                {unreadCount}
                              </span>
                            ) : null}
                          </>
                        ) : isSectionLocked ? (
                          <span className="absolute top-1.5 right-1.5">
                            <Lock size={10} weight="bold" className="text-[var(--rl-text-muted)]" />
                          </span>
                        ) : item.href === "/inbox" && unreadCount > 0 ? (
                          <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-[var(--rl-red)]" />
                        ) : null}
                      </Link>
                    );

                    if (isCollapsed) {
                      return (
                        <Tooltip key={item.href} content={isSectionLocked ? `${item.label} (Admin only)` : item.label}>
                          {navLink}
                        </Tooltip>
                      );
                    }

                    return navLink;
                  })}
                </div>
              );
            })}
          </nav>
        </aside>

        {/* Main Content Area */}
        <main className="min-w-0 w-full animate-fade-in">{children}</main>
      </div>

      {/* Global AI Copilot */}
      <GlobalAiCopilot />
    </div>
  );
}
