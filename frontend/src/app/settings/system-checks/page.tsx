"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  ArrowsClockwise,
  CheckCircle,
  ShieldCheck,
  ArrowSquareOut,
  Pulse,
  Database,
  Compass,
  Cpu,
} from "@phosphor-icons/react";
import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

type Check = { name: string; status: string; message: string; group?: string };
type DomainCheck = { name: string; status: string; message: string; module: string };
type SitemapRoute = {
  category: string;
  title: string;
  route: string;
  api_endpoint: string;
  status: string;
  description: string;
};
type DatabaseSummary = {
  active_companies: number;
  active_products: number;
  published_catalogs: number;
  active_benefit_concepts: number;
  active_benefit_aliases: number;
  live_sessions: number;
  sandbox_test_sessions: number;
  active_tenures: number;
};

type ProbeResult = {
  ok: boolean;
  ms: number;
  detail: string;
};

const LIVE_API_PROBES: Array<{ key: string; label: string; path: string }> = [
  { key: "/upload", label: "Upload & Gemini Quota", path: "/settings/limits" },
  { key: "/sessions", label: "Sessions & Sandbox Feed", path: "/sessions?limit=1" },
  { key: "/builder/global-benefits", label: "Global Benefit Concepts", path: "/business/benefit-concepts?page=1&page_size=5" },
  { key: "/builder/templates/quotation-templates", label: "Published Templates", path: "/templates/published" },
  { key: "/settings/extraction/road-tax", label: "JPJ Road Tax Rules", path: "/road-tax/rules" },
  { key: "/settings/system-checks", label: "Database Health", path: "/health" },
];

function isReadyStatus(status?: string): boolean {
  const s = (status || "").toLowerCase();
  return s === "ready" || s === "ok" || s === "available";
}

export default function SettingsSystemChecksPage() {
  const [checks, setChecks] = useState<Check[]>([]);
  const [domainChecks, setDomainChecks] = useState<DomainCheck[]>([]);
  const [sitemapRoutes, setSitemapRoutes] = useState<SitemapRoute[]>([]);
  const [dbSummary, setDbSummary] = useState<DatabaseSummary | null>(null);
  const [probeMap, setProbeMap] = useState<Record<string, ProbeResult>>({});
  const [loading, setLoading] = useState(true);
  const [probing, setProbing] = useState(false);
  const [error, setError] = useState("");

  const runLiveApiProbes = useCallback(async () => {
    setProbing(true);
    const results: Record<string, ProbeResult> = {};
    await Promise.all(
      LIVE_API_PROBES.map(async (item) => {
        const t0 = performance.now();
        try {
          await api(item.path);
          const ms = Math.round(performance.now() - t0);
          results[item.key] = { ok: true, ms, detail: `HTTP 200 · ${ms}ms` };
        } catch (err: any) {
          const ms = Math.round(performance.now() - t0);
          results[item.key] = {
            ok: false,
            ms,
            detail: err?.message || "Probe failed",
          };
        }
      })
    );
    setProbeMap(results);
    setProbing(false);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await api<{
        checks: Check[];
        domain_logic_checks?: DomainCheck[];
        sitemap_routes?: SitemapRoute[];
        database_summary?: DatabaseSummary;
      }>("/system/checks");
      setChecks(result.checks || []);
      setDomainChecks(result.domain_logic_checks || []);
      setSitemapRoutes(result.sitemap_routes || []);
      if (result.database_summary) setDbSummary(result.database_summary);
      await runLiveApiProbes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load system checks.");
    } finally {
      setLoading(false);
    }
  }, [runLiveApiProbes]);

  useEffect(() => {
    load();
  }, [load]);

  const required = checks.filter((check) => (check.group || "Required Setup") === "Required Setup");
  const advanced = checks.filter((check) => check.group === "Advanced Enhanced Reading");
  const domainReadyCount = domainChecks.filter((c) => isReadyStatus(c.status)).length;

  return (
    <AppShell>
      <section className="grid gap-6 max-w-[1440px] mx-auto">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[28px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">
              System Health, Logic Diagnostics &amp; Sitemap
            </h1>
            <p className="text-[13px] text-[var(--rl-text-muted)]">
              Automated live verification of infrastructure, actuarial math engines, benefit alias grounding, sandbox isolation, and API endpoints.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              loading={probing}
              icon={<Pulse size={15} weight="bold" />}
              onClick={runLiveApiProbes}
            >
              Probe Live APIs
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={loading}
              icon={<ArrowsClockwise size={15} weight="bold" />}
              onClick={load}
            >
              Run Full Diagnostic
            </Button>
          </div>
        </div>

        <SettingsNav />

        {error ? (
          <div
            role="alert"
            className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3.5 py-2.5 text-xs font-semibold text-[var(--rl-red)]"
          >
            {error}
          </div>
        ) : null}

        {/* Live Database & Catalog Telemetry Summary */}
        {dbSummary ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-2.5">
            {[
              { label: "Active Insurers", value: dbSummary.active_companies },
              { label: "Active Products", value: dbSummary.active_products },
              { label: "Published Catalogs", value: dbSummary.published_catalogs },
              { label: "Benefit Concepts", value: dbSummary.active_benefit_concepts },
              { label: "Benefit Aliases", value: dbSummary.active_benefit_aliases },
              { label: "Live Renewal Tenures", value: dbSummary.active_tenures },
              { label: "Live Sessions", value: dbSummary.live_sessions },
              { label: "Sandbox Test Dump", value: dbSummary.sandbox_test_sessions },
            ].map((stat) => (
              <Card key={stat.label} className="p-3 flex flex-col justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                  {stat.label}
                </span>
                <span className="mt-1 font-mono text-xl font-bold text-[var(--rl-text-strong)]">
                  {stat.value.toLocaleString()}
                </span>
              </Card>
            ))}
          </div>
        ) : null}

        {/* Section 1: Domain Logic & Actuarial Self-Tests */}
        {domainChecks.length > 0 ? (
          <Card className="p-5 space-y-3">
            <div className="flex items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-3">
              <div className="flex items-center gap-2">
                <Cpu size={18} weight="bold" className="text-[var(--rl-text-strong)]" />
                <div>
                  <h2 className="text-base font-bold text-[var(--rl-text-strong)]">
                    Domain Logic &amp; Invariant Self-Tests
                  </h2>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Executes real-time assertions against Road Tax, Betterment, Reranking, 559 Benefit Aliases, Sandbox Firewall, and 8K Design 2 assets.
                  </p>
                </div>
              </div>
              <Badge variant={domainReadyCount === domainChecks.length ? "success" : "warning"}>
                {domainReadyCount}/{domainChecks.length} Passing
              </Badge>
            </div>

            <div className="divide-y divide-[var(--rl-border)]">
              {domainChecks.map((dc) => (
                <div
                  key={dc.name}
                  className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-bold text-[var(--rl-text-strong)]">{dc.name}</span>
                      <code className="text-[10px] font-mono bg-neutral-100 border border-[var(--rl-border)] px-1.5 py-0.2 rounded text-[var(--rl-text-muted)]">
                        {dc.module}
                      </code>
                    </div>
                    <p className="text-xs text-[var(--rl-text-muted)] font-mono">{dc.message}</p>
                  </div>
                  <StatusBadge status={dc.status} />
                </div>
              ))}
            </div>
          </Card>
        ) : null}

        {/* Section 2: Interactive System Sitemap & Live API Probe Matrix */}
        {sitemapRoutes.length > 0 ? (
          <Card className="p-5 space-y-4">
            <div className="flex items-center justify-between gap-2 border-b border-[var(--rl-border)] pb-3">
              <div className="flex items-center gap-2">
                <Compass size={18} weight="bold" className="text-[var(--rl-text-strong)]" />
                <div>
                  <h2 className="text-base font-bold text-[var(--rl-text-strong)]">
                    Interactive System Sitemap &amp; API Health Matrix
                  </h2>
                  <p className="text-xs text-[var(--rl-text-muted)]">
                    Direct navigation and live API latency probe across every workspace, studio, and operational module.
                  </p>
                </div>
              </div>
              <Badge variant="success">{sitemapRoutes.length} Active Modules</Badge>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {sitemapRoutes.map((item) => {
                const probe = probeMap[item.route];
                return (
                  <div
                    key={`${item.title}-${item.route}`}
                    className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-bg)]/50 p-3.5 flex flex-col justify-between gap-3 hover:border-[var(--rl-black)] transition-colors"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                          {item.category}
                        </span>
                        {probe ? (
                          <Badge variant={probe.ok ? "success" : "danger"}>{probe.detail}</Badge>
                        ) : (
                          <Badge variant="success">{item.status}</Badge>
                        )}
                      </div>
                      <h3 className="text-sm font-bold text-[var(--rl-text-strong)]">{item.title}</h3>
                      <p className="text-xs text-[var(--rl-text-muted)] leading-relaxed">{item.description}</p>
                    </div>

                    <div className="pt-2 border-t border-[var(--rl-border)] flex items-center justify-between gap-2">
                      <code className="text-[10px] font-mono text-[var(--rl-text-muted)] truncate">
                        {item.api_endpoint}
                      </code>
                      <Link
                        href={item.route as Route}
                        className="inline-flex items-center gap-1 text-xs font-bold text-[var(--rl-text-strong)] hover:text-[var(--rl-red)] shrink-0"
                      >
                        <span>Open</span>
                        <ArrowSquareOut size={13} weight="bold" />
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        ) : null}

        {/* Section 3: Infrastructure & Required Setup */}
        <CheckGroup title="Required Infrastructure & Providers" checks={required} />

        <Card>
          <details className="p-5">
            <summary className="cursor-pointer text-base font-bold text-[var(--rl-text-strong)]">
              Advanced Enhanced Reading (Optional Local OCR Binaries)
            </summary>
            <p className="mt-1.5 text-xs text-[var(--rl-text-muted)]">
              Optional local OCR engines; primary multimodal PDF extraction runs via the Gemini AI Fleet.
            </p>
            <div className="mt-3">
              <CheckRows checks={advanced} />
            </div>
          </details>
        </Card>
      </section>
    </AppShell>
  );
}

function CheckGroup({ title, checks }: { title: string; checks: Check[] }) {
  const okCount = checks.filter((c) => isReadyStatus(c.status)).length;
  return (
    <Card>
      <div className="p-5">
        <div className="flex items-center justify-between gap-2.5 border-b border-[var(--rl-border)] pb-3">
          <div className="flex items-center gap-2">
            <Database size={18} weight="bold" className="text-[var(--rl-text-strong)]" />
            <h2 className="text-base font-bold text-[var(--rl-text-strong)]">{title}</h2>
          </div>
          <Badge variant={okCount === checks.length && checks.length > 0 ? "success" : "warning"}>
            {okCount}/{checks.length} Ready
          </Badge>
        </div>
        <div className="mt-2">
          <CheckRows checks={checks} />
        </div>
      </div>
    </Card>
  );
}

function CheckRows({ checks }: { checks: Check[] }) {
  return (
    <div className="divide-y divide-[var(--rl-border)]">
      {checks.map((check) => (
        <div key={check.name} className="grid gap-2 py-3 sm:grid-cols-[1fr_auto] items-center">
          <div>
            <div className="text-sm font-bold text-[var(--rl-text-strong)]">{check.name}</div>
            <div className="text-xs text-[var(--rl-text-muted)]">{check.message}</div>
          </div>
          <StatusBadge status={check.status} />
        </div>
      ))}
    </div>
  );
}
