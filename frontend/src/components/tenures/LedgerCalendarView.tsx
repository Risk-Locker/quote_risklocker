"use client";

import React from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  CalendarBlank,
  ListDashes,
  CalendarCheck,
  Columns,
  ArrowRight,
  ArrowSquareOut,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { getVehicleDisplayName } from "@/lib/vehicle-utils";
import type { CalendarEvent } from "./types";
import { formatDateSafe } from "./types";

export interface LedgerCalendarViewProps {
  calendarData: {
    firstDay: number;
    daysInMonth: number;
    monthLabel: string;
    year: number;
    month: number;
    dayMap: Record<number, CalendarEvent[]>;
    agendaDays: Array<{ day: number; dateStr: string; items: CalendarEvent[] }>;
  };
  calendarVehicleFilter: string;
  setCalendarVehicleFilter: (val: string) => void;
  calendarVehicleOptions: string[];
  loadingCalendar: boolean;
  calendarDisplay: "grid" | "agenda";
  setCalendarDisplay: (val: "grid" | "agenda") => void;
  onOpenDrawer: (tenureId: string) => void;
}

export function LedgerCalendarView({
  calendarData,
  calendarVehicleFilter,
  setCalendarVehicleFilter,
  calendarVehicleOptions,
  loadingCalendar,
  calendarDisplay,
  setCalendarDisplay,
  onOpenDrawer,
}: LedgerCalendarViewProps) {
  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="text-sm font-bold text-neutral-900">
            {calendarData.monthLabel}
          </span>
          <span className="text-xs font-medium text-neutral-500">
            · {calendarData.agendaDays.reduce((acc, g) => acc + g.items.length, 0)} timeline events (
            {calendarData.agendaDays.reduce(
              (acc, g) => acc + g.items.filter((i) => i.type === "start").length,
              0
            )}{" "}
            starting ·{" "}
            {calendarData.agendaDays.reduce(
              (acc, g) => acc + g.items.filter((i) => i.type === "end").length,
              0
            )}{" "}
            expiring ·{" "}
            {calendarData.agendaDays.reduce(
              (acc, g) => acc + g.items.filter((i) => i.type === "session").length,
              0
            )}{" "}
            quotes)
          </span>

          {/* Vehicle Filter Selector */}
          <div className="flex items-center gap-1.5 ml-1">
            <label className="text-xs font-bold text-neutral-600">Vehicle:</label>
            <select
              value={calendarVehicleFilter}
              onChange={(e) => setCalendarVehicleFilter(e.target.value)}
              className="h-7 px-2 text-xs font-mono font-bold rounded-[var(--rl-radius-sm)] border border-neutral-300 bg-white text-neutral-800"
            >
              <option value="all">All Vehicles ({calendarVehicleOptions.length})</option>
              {calendarVehicleOptions.map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </select>
            {loadingCalendar && (
              <span className="text-xs text-blue-600 font-semibold animate-pulse">
                Loading quotes...
              </span>
            )}
          </div>
        </div>

        <div className="flex items-center rounded-[var(--rl-radius-sm)] border border-neutral-200 bg-neutral-100 p-0.5 shrink-0">
          <button
            type="button"
            onClick={() => setCalendarDisplay("grid")}
            className={`px-2.5 py-1 text-xs font-semibold rounded-[var(--rl-radius-sm)] transition-all flex items-center gap-1 ${calendarDisplay === "grid"
              ? "bg-white text-neutral-900 shadow-2xs"
              : "text-neutral-500 hover:text-neutral-800"
              }`}
          >
            <CalendarBlank size={13} weight="bold" />
            <span>Month Grid</span>
          </button>
          <button
            type="button"
            onClick={() => setCalendarDisplay("agenda")}
            className={`px-2.5 py-1 text-xs font-semibold rounded-[var(--rl-radius-sm)] transition-all flex items-center gap-1 ${calendarDisplay === "agenda"
              ? "bg-white text-neutral-900 shadow-2xs"
              : "text-neutral-500 hover:text-neutral-800"
              }`}
          >
            <ListDashes size={13} weight="bold" />
            <span>Agenda List</span>
          </button>
        </div>
      </div>

      {/* Month Grid */}
      {calendarDisplay === "grid" && (
        <div className="bg-white border border-neutral-200/90 rounded-[var(--rl-radius)] p-3 shadow-2xs">
          <div className="grid grid-cols-7 gap-2 pb-2 border-b border-neutral-100 text-center text-[11px] font-bold uppercase tracking-wider text-neutral-400">
            <span>Sun</span>
            <span>Mon</span>
            <span>Tue</span>
            <span>Wed</span>
            <span>Thu</span>
            <span>Fri</span>
            <span>Sat</span>
          </div>

          <div className="grid grid-cols-7 gap-2 pt-2">
            {Array.from({ length: calendarData.firstDay }).map((_, idx) => (
              <div
                key={`blank-${idx}`}
                className="min-h-[105px] rounded-[var(--rl-radius-sm)] bg-neutral-50/40 border border-dashed border-neutral-150/60"
              />
            ))}

            {Array.from({ length: calendarData.daysInMonth }).map((_, idx) => {
              const dayNum = idx + 1;
              const dayTenures = calendarData.dayMap[dayNum] || [];
              const isToday =
                new Date().getFullYear() === calendarData.year &&
                new Date().getMonth() === calendarData.month &&
                new Date().getDate() === dayNum;

              return (
                <div
                  key={`day-${dayNum}`}
                  className={`min-h-[105px] p-1.5 rounded-[var(--rl-radius-sm)] border flex flex-col transition-all ${isToday
                    ? "bg-blue-50/20 border-blue-400/80 ring-1 ring-blue-300"
                    : dayTenures.length > 0
                      ? "bg-white border-neutral-200 shadow-2xs"
                      : "bg-neutral-50/30 border-neutral-150"
                    }`}
                >
                  <div className="flex items-center justify-between pb-1 border-b border-neutral-100/60 mb-1">
                    <span
                      className={`text-xs font-bold px-1.5 py-0.2 rounded ${isToday ? "bg-blue-600 text-white" : "text-neutral-700"
                        }`}
                    >
                      {dayNum}
                    </span>

                    {dayTenures.length > 0 && (
                      <span className="text-[10px] font-bold text-neutral-600 bg-neutral-100 px-1.5 py-0.2 rounded-full">
                        {dayTenures.length}
                      </span>
                    )}
                  </div>

                  <div className="flex-1 space-y-1 overflow-y-auto max-h-[110px] scrollbar-thin">
                    {dayTenures.map((item, itemIdx) => {
                      if (item.type === "session") {
                        const s = item.session;
                        return (
                          <div
                            key={`sess-${s.session_id}-${itemIdx}`}
                            className="p-1.5 bg-blue-50/70 hover:bg-blue-100/90 border border-blue-200/90 rounded transition-all text-[11px]"
                          >
                            <div className="flex items-center justify-between gap-1">
                              <span className="text-[9px] font-bold px-1 py-0.2 rounded uppercase shrink-0 bg-blue-100 text-blue-800 border border-blue-200">
                                Quote
                              </span>
                              <span
                                className="font-bold text-neutral-900 font-mono truncate text-[11px]"
                                title={s.vehicle_no}
                              >
                                {s.vehicle_no}
                              </span>
                            </div>
                            <p className="text-[10px] text-blue-900 truncate mt-0.5 font-medium">
                              {s.detected_company || "Underwriter"}
                            </p>
                            <div className="flex items-center justify-between gap-1 pt-1 mt-1 border-t border-blue-200/50">
                              <span className="text-[9px] font-bold text-neutral-700 font-mono">
                                {s.total_payable
                                  ? `RM ${s.total_payable}`
                                  : s.sum_insured
                                    ? `SI: RM ${s.sum_insured}`
                                    : "—"}
                              </span>
                              {s.tenure_id ? (
                                <Link
                                  href={`/comparison?tenure_id=${s.tenure_id}` as Route}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-amber-500 hover:bg-amber-600 text-slate-950 text-[9px] font-bold transition-colors"
                                >
                                  <Columns className="w-2.5 h-2.5" />
                                  <span>Compare</span>
                                </Link>
                              ) : (
                                <Link
                                  href={`/sessions/${s.session_id}/review` as Route}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-neutral-200 hover:bg-neutral-300 text-neutral-800 text-[9px] font-bold transition-colors"
                                >
                                  <ArrowSquareOut className="w-2.5 h-2.5" />
                                  <span>Review</span>
                                </Link>
                              )}
                            </div>
                          </div>
                        );
                      }

                      const t = item.tenure;
                      const isStart = item.type === "start";
                      const displayName = getVehicleDisplayName(t.vehicle_no, t.chassis_no);

                      return (
                        <div
                          key={`${t.id}-${item.type}-${itemIdx}`}
                          onClick={() => onOpenDrawer(t.id)}
                          className="p-1.5 bg-neutral-50 hover:bg-neutral-100/90 border border-neutral-200/80 rounded cursor-pointer transition-all hover:shadow-xs group text-[11px]"
                        >
                          <div className="flex items-center justify-between gap-1">
                            <span
                              className={`text-[9px] font-bold px-1 py-0.2 rounded uppercase shrink-0 ${isStart
                                ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                : "bg-rose-100 text-rose-800 border border-rose-200"
                                }`}
                            >
                              {isStart ? "Start" : "Exp"}
                            </span>
                            <span
                              className="font-bold text-neutral-900 font-mono truncate text-[11px]"
                              title={displayName}
                            >
                              {displayName}
                            </span>
                          </div>

                          <p className="text-[10px] text-neutral-500 truncate mt-0.5">
                            {t.customer_name}
                          </p>

                          <div className="flex items-center justify-between gap-1 pt-1 mt-1 border-t border-neutral-200/50">
                            <span className="text-[9px] text-neutral-400">
                              {t.sourced_quotes.length} quotes
                            </span>
                            <Link
                              href={`/comparison?tenure_id=${t.id}` as Route}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-amber-500 hover:bg-amber-600 text-slate-950 text-[9px] font-bold transition-colors"
                            >
                              <Columns className="w-2.5 h-2.5" />
                              <span>Compare</span>
                            </Link>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Agenda List */}
      {calendarDisplay === "agenda" && (
        <div className="space-y-3">
          {calendarData.agendaDays.length === 0 ? (
            <div className="bg-white border border-neutral-200 rounded-[var(--rl-radius)] p-12 text-center text-xs text-neutral-400">
              No policy start or expiry dates recorded for {calendarData.monthLabel}.
            </div>
          ) : (
            calendarData.agendaDays.map((group) => (
              <div
                key={group.day}
                className="bg-white border border-neutral-200/90 rounded-[var(--rl-radius)] overflow-hidden shadow-2xs"
              >
                <div className="px-4 py-2 bg-neutral-50/80 border-b border-neutral-200/70 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <CalendarCheck className="w-4 h-4 text-neutral-600" />
                    <span className="text-xs font-bold text-neutral-900">{group.dateStr}</span>
                  </div>
                  <span className="text-[11px] font-semibold text-neutral-500">
                    {group.items.length} {group.items.length === 1 ? "Event" : "Events"} (
                    {group.items.filter((i) => i.type === "start").length} Starts ·{" "}
                    {group.items.filter((i) => i.type === "end").length} Expiries)
                  </span>
                </div>

                <div className="divide-y divide-neutral-100 p-2">
                  {group.items.map((item, itemIdx) => {
                    if (item.type === "session") {
                      const s = item.session;
                      return (
                        <div
                          key={`agenda-sess-${s.session_id}-${itemIdx}`}
                          className="p-3 hover:bg-blue-50/40 rounded-lg transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 border border-blue-100/60"
                        >
                          <div className="space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded uppercase bg-blue-100 text-blue-800 border border-blue-200">
                                Quotation Uploaded
                              </span>
                              <span className="font-bold text-sm text-neutral-900 font-mono">
                                {s.vehicle_no}
                              </span>
                              <span className="text-xs text-neutral-400">·</span>
                              <span className="text-xs font-semibold text-neutral-700">
                                {s.detected_company || "Underwriter"}
                              </span>
                              <span className="text-xs text-neutral-400">·</span>
                              <span className="text-xs font-medium text-neutral-600">
                                {s.customer_name}
                              </span>
                            </div>

                            <div className="flex items-center gap-2 text-xs text-neutral-500 flex-wrap">
                              <span>Quotation Date:</span>
                              <strong className="font-mono text-neutral-800">{s.quotation_date}</strong>
                              <span className="text-neutral-400">·</span>
                              <span>Total Payable:</span>
                              <strong className="font-mono text-emerald-700">
                                {s.total_payable
                                  ? `RM ${s.total_payable}`
                                  : s.sum_insured
                                    ? `SI: RM ${s.sum_insured}`
                                    : "—"}
                              </strong>
                            </div>
                          </div>

                          <div className="flex items-center gap-2 shrink-0">
                            {s.tenure_id ? (
                              <Link
                                href={`/comparison?tenure_id=${s.tenure_id}` as Route}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-colors shadow-2xs"
                              >
                                <Columns className="w-3.5 h-3.5" />
                                <span>Marketing Comparison</span>
                              </Link>
                            ) : (
                              <Link
                                href={`/sessions/${s.session_id}/review` as Route}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-neutral-100 hover:bg-neutral-200 text-neutral-800 text-xs font-bold transition-colors"
                              >
                                <ArrowSquareOut className="w-3.5 h-3.5" />
                                <span>Review Session</span>
                              </Link>
                            )}
                          </div>
                        </div>
                      );
                    }

                    const t = item.tenure;
                    const isStart = item.type === "start";
                    const displayName = getVehicleDisplayName(t.vehicle_no, t.chassis_no);

                    return (
                      <div
                        key={`${t.id}-${item.type}-${itemIdx}`}
                        onClick={() => onOpenDrawer(t.id)}
                        className="p-3 hover:bg-neutral-50/70 rounded-lg cursor-pointer transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span
                              className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase ${isStart
                                ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                : "bg-rose-100 text-rose-800 border border-rose-200"
                                }`}
                            >
                              {isStart ? "Policy Start" : "Policy Expiry"}
                            </span>
                            <span className="font-bold text-sm text-neutral-900 font-mono">
                              {displayName}
                            </span>
                            <span className="text-xs text-neutral-400">·</span>
                            <span className="text-xs font-medium text-neutral-700">
                              {t.customer_name}
                            </span>
                            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
                              {t.stage || "Quotations"}
                            </span>
                          </div>

                          <div className="flex items-center gap-2 text-xs text-neutral-500 flex-wrap">
                            <span>Coverage:</span>
                            {t.stage === "Issue Policy" && t.coverage_start_date ? (
                              <strong className="font-mono text-neutral-800">
                                {formatDateSafe(t.coverage_start_date)} –{" "}
                                {formatDateSafe(t.coverage_end_date)}
                              </strong>
                            ) : (
                              <span className="italic text-neutral-400">
                                Pending Issue (Confirmed on Policy Issue)
                              </span>
                            )}
                            <span className="text-neutral-400">·</span>
                            <span>{t.sourced_quotes.length} Quotes</span>
                            {t.sub_agent_name && (
                              <>
                                <span className="text-neutral-400">·</span>
                                <span className="text-emerald-700 font-medium">
                                  PIC: {t.sub_agent_name}
                                </span>
                              </>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-2 shrink-0">
                          <Link
                            href={`/comparison?tenure_id=${t.id}` as Route}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-600 text-slate-950 text-xs font-bold transition-colors shadow-2xs"
                          >
                            <Columns className="w-3.5 h-3.5" />
                            <span>Marketing Comparison</span>
                          </Link>

                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={(e) => {
                              e.stopPropagation();
                              onOpenDrawer(t.id);
                            }}
                            className="h-8 text-xs font-medium cursor-pointer"
                          >
                            Logs &amp; Activity <ArrowRight className="w-3.5 h-3.5 ml-1" />
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
