"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Route } from "next";
import {
  Car,
  ClockCounterClockwise,
  MagnifyingGlass,
  Columns,
  ArrowsClockwise,
  CheckCircle,
  Clock,
  ArrowRight,
  ShieldCheck,
  CalendarBlank,
  Users,
  FunnelSimple,
  Plus,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { TenureTimelineDrawer } from "@/components/tenures/tenure-timeline-drawer";

interface SourcedQuote {
  session_id: string;
  company: string;
  version: number;
  total_payable: string | null;
  sum_insured: string | null;
}

interface TenureItem {
  id: string;
  vehicle_no: string;
  customer_name: string;
  coverage_start_date: string;
  coverage_end_date: string;
  expiry_month: string;
  status: string;
  stage: string;
  sub_agent_name?: string | null;
  road_tax: number;
  runner_fee: number;
  winning_company_name?: string | null;
  won_premium?: number | null;
  sourced_quotes: SourcedQuote[];
  created_at: string;
  updated_at: string;
}

export default function SessionsPage() {
  const router = useRouter();
  const [tenures, setTenures] = useState<TenureItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [activeDrawerTenureId, setActiveDrawerTenureId] = useState<string | null>(null);

  const fetchTenures = useCallback(async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      params.set("page", "1");
      params.set("page_size", "100");
      if (search.trim()) {
        params.set("search", search.trim());
      }
      if (statusFilter !== "all") {
        params.set("status", statusFilter);
      }
      const res = await api<{ tenures: TenureItem[]; total: number }>(`/tenures?${params.toString()}`);
      setTenures(res.tenures || []);
    } catch {
      setTenures([]);
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    fetchTenures();
  }, [fetchTenures]);

  const stats = useMemo(() => {
    const total = tenures.length;
    const withQuotes = tenures.filter((t) => t.sourced_quotes && t.sourced_quotes.length > 0).length;
    const won = tenures.filter((t) => t.status === "hit" || t.stage === "Close - Win").length;
    const totalQuotes = tenures.reduce((acc, t) => acc + (t.sourced_quotes?.length || 0), 0);
    return { total, withQuotes, won, totalQuotes };
  }, [tenures]);

  return (
    <AppShell>
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Header Ribbon */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-200/80 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-600 mb-1">
              <ClockCounterClockwise size={16} weight="bold" />
              <span>Multi-Quote Comparison Ledger</span>
            </div>
            <h1 className="text-2xl font-black tracking-tight text-neutral-900">
              Comparison Sessions
            </h1>
            <p className="text-xs text-neutral-500 mt-0.5">
              Browse, resume, and track active underwriter comparison deals across vehicles
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="secondary"
              onClick={() => fetchTenures()}
              className="text-xs font-semibold h-9 px-3 gap-1.5 cursor-pointer shadow-2xs"
            >
              <ArrowsClockwise size={14} weight="bold" className={loading ? "animate-spin" : ""} />
              <span>Refresh</span>
            </Button>
            <Button
              type="button"
              onClick={() => router.push("/upload/marketing-comparison" as Route)}
              className="text-xs font-bold h-9 px-4 bg-[#1b1717] hover:bg-black text-white gap-1.5 cursor-pointer shadow-2xs"
            >
              <Plus size={14} weight="bold" />
              <span>New Comparison Upload</span>
            </Button>
          </div>
        </div>

        {/* Metric Summary Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="bg-white p-3.5 rounded-xl border border-neutral-200/80 shadow-2xs">
            <span className="text-[11px] font-bold text-neutral-400 uppercase tracking-wider">Total Deals</span>
            <div className="text-xl font-black text-neutral-900 mt-1">{stats.total}</div>
          </div>
          <div className="bg-white p-3.5 rounded-xl border border-neutral-200/80 shadow-2xs">
            <span className="text-[11px] font-bold text-amber-600 uppercase tracking-wider">With Quotes</span>
            <div className="text-xl font-black text-amber-700 mt-1">{stats.withQuotes}</div>
          </div>
          <div className="bg-white p-3.5 rounded-xl border border-neutral-200/80 shadow-2xs">
            <span className="text-[11px] font-bold text-emerald-600 uppercase tracking-wider">Won Policies</span>
            <div className="text-xl font-black text-emerald-700 mt-1">{stats.won}</div>
          </div>
          <div className="bg-white p-3.5 rounded-xl border border-neutral-200/80 shadow-2xs">
            <span className="text-[11px] font-bold text-neutral-500 uppercase tracking-wider">Total Sourced</span>
            <div className="text-xl font-black text-neutral-800 mt-1">{stats.totalQuotes} Quotes</div>
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div className="bg-white p-3 rounded-xl border border-neutral-200/80 shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="relative w-full sm:w-80">
            <MagnifyingGlass size={15} weight="bold" className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search plate, customer, IC..."
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-neutral-200 bg-neutral-50/60 focus:bg-white focus:outline-none focus:ring-1 focus:ring-black"
            />
          </div>

          <div className="flex items-center gap-1.5 w-full sm:w-auto overflow-x-auto">
            <span className="text-xs text-neutral-400 font-semibold mr-1 flex items-center gap-1">
              <FunnelSimple size={13} weight="bold" /> Status:
            </span>
            {["all", "draft", "quoted", "hit", "miss"].map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1 text-xs font-bold rounded-lg capitalize transition-colors cursor-pointer ${
                  statusFilter === st
                    ? "bg-[#1b1717] text-white"
                    : "bg-neutral-100 text-neutral-600 hover:bg-neutral-200"
                }`}
              >
                {st}
              </button>
            ))}
          </div>
        </div>

        {/* Sessions List */}
        {loading ? (
          <div className="bg-white rounded-2xl border border-neutral-200/80 p-12 text-center text-xs text-neutral-500 shadow-2xs">
            <ArrowsClockwise size={24} className="animate-spin mx-auto mb-2 text-neutral-400" />
            <span>Loading comparison sessions...</span>
          </div>
        ) : tenures.length === 0 ? (
          <div className="bg-white rounded-2xl border-2 border-dashed border-neutral-200 p-12 text-center flex flex-col items-center justify-center gap-3">
            <div className="size-12 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center">
              <Columns size={24} weight="duotone" />
            </div>
            <h3 className="text-base font-bold text-neutral-900">No Comparison Sessions Found</h3>
            <p className="text-xs text-neutral-500 max-w-sm">
              {search
                ? `No sessions match "${search}". Try resetting the search.`
                : "No active comparison sessions yet. Upload quotes or create a deal from the Renewal Ledger to get started."}
            </p>
            {search && (
              <Button type="button" variant="secondary" size="sm" onClick={() => setSearch("")}>
                Clear Search
              </Button>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {tenures.map((t) => {
              const quotes = t.sourced_quotes || [];
              const companies = Array.from(new Set(quotes.map((q) => q.company).filter(Boolean)));
              const isWon = t.status === "hit" || t.stage === "Close - Win";

              return (
                <div
                  key={t.id}
                  className="bg-white rounded-xl border border-neutral-200/80 hover:border-neutral-300 p-4 shadow-2xs hover:shadow-xs transition-all flex flex-col md:flex-row md:items-center justify-between gap-4 group"
                >
                  {/* Left: Vehicle & Client Details */}
                  <div className="flex items-start gap-3.5 min-w-[280px]">
                    <div className="size-10 rounded-xl bg-neutral-100 border border-neutral-200 flex items-center justify-center text-neutral-800 shrink-0 group-hover:bg-[#1b1717] group-hover:text-white transition-colors">
                      <Car size={20} weight="bold" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-black text-sm text-neutral-900 tracking-wide">
                          {t.vehicle_no}
                        </span>
                        <span
                          className={`text-[10px] font-bold px-2 py-0.5 rounded-full capitalize ${
                            isWon
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                              : t.status === "quoted"
                              ? "bg-blue-100 text-blue-800 border border-blue-200"
                              : "bg-neutral-100 text-neutral-700 border border-neutral-200"
                          }`}
                        >
                          {t.status || "draft"}
                        </span>
                        {t.stage && (
                          <span className="text-[10px] font-medium text-neutral-500 bg-neutral-50 px-1.5 py-0.5 rounded border border-neutral-200">
                            {t.stage}
                          </span>
                        )}
                      </div>

                      <p className="text-xs font-semibold text-neutral-800 mt-0.5">
                        {t.customer_name}
                      </p>

                      <div className="flex items-center gap-2 text-[11px] text-neutral-400 mt-1">
                        <span className="flex items-center gap-1 font-mono">
                          <CalendarBlank size={12} />
                          {t.coverage_start_date?.split("T")[0] || "—"} to {t.coverage_end_date?.split("T")[0] || "—"}
                        </span>
                        {t.sub_agent_name && (
                          <>
                            <span>·</span>
                            <span className="text-emerald-700 font-medium">PIC: {t.sub_agent_name}</span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Middle: Sourced Insurers */}
                  <div className="flex-1 min-w-[220px]">
                    <div className="text-[11px] font-bold text-neutral-400 uppercase tracking-wider mb-1.5 flex items-center gap-1.5">
                      <span>Underwriters ({quotes.length})</span>
                      {isWon && t.winning_company_name && (
                        <span className="text-emerald-700 font-bold normal-case flex items-center gap-1">
                          <ShieldCheck size={13} weight="fill" /> Winner: {t.winning_company_name}
                        </span>
                      )}
                    </div>
                    {companies.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5">
                        {companies.map((cName) => (
                          <span
                            key={cName}
                            className="text-xs font-semibold px-2 py-0.5 rounded-lg bg-neutral-100 text-neutral-800 border border-neutral-200/80"
                          >
                            {cName}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-xs text-neutral-400 italic">No quotation documents uploaded yet</span>
                    )}
                  </div>

                  {/* Right: Actions */}
                  <div className="flex items-center gap-2 shrink-0">
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={() => setActiveDrawerTenureId(t.id)}
                      className="h-9 px-3 text-xs font-medium cursor-pointer"
                    >
                      Timeline
                    </Button>
                    <Link
                      href={`/comparison?tenure_id=${t.id}` as Route}
                      className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-colors shadow-2xs cursor-pointer"
                    >
                      <Columns size={14} weight="bold" />
                      <span>Resume</span>
                      <ArrowRight size={13} weight="bold" />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Slide-out Interactive Tenure Timeline Drawer */}
        {activeDrawerTenureId && (
          <TenureTimelineDrawer
            tenureId={activeDrawerTenureId}
            isOpen={Boolean(activeDrawerTenureId)}
            onClose={() => setActiveDrawerTenureId(null)}
          />
        )}
      </div>
    </AppShell>
  );
}
