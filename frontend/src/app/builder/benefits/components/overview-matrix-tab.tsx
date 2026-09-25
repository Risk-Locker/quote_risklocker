"use client";

import React, { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import {
  Check,
  FileDoc,
  FileXls,
  MagnifyingGlass,
  PencilSimple,
  Plus,
  ShieldCheck,
  Sparkle,
  X,
} from "@phosphor-icons/react";
import type { CompanyMatrixData } from "../types";

export interface OverviewMatrixTabProps {
  matrixData: CompanyMatrixData | null;
  matrixLoading: boolean;
  matrixFilterCoverage: string;
  setMatrixFilterCoverage: (val: string) => void;
  matrixSearch: string;
  setMatrixSearch: (val: string) => void;
  downloadDocx: () => void;
  downloadXlsx: () => void;
  editingMatrixItem: {
    catalog_id: string;
    offering_id: string;
    field: "display_value" | "description";
    value: string;
  } | null;
  setEditingMatrixItem: React.Dispatch<
    React.SetStateAction<{
      catalog_id: string;
      offering_id: string;
      field: "display_value" | "description";
      value: string;
    } | null>
  >;
  saveMatrixInlineEdit: () => Promise<void>;
}

export function OverviewMatrixTab({
  matrixData,
  matrixLoading,
  matrixFilterCoverage,
  setMatrixFilterCoverage,
  matrixSearch,
  setMatrixSearch,
  downloadDocx,
  downloadXlsx,
  editingMatrixItem,
  setEditingMatrixItem,
  saveMatrixInlineEdit,
}: OverviewMatrixTabProps) {
  const filteredMatrixScenarios = useMemo(() => {
    if (!matrixData) return [];
    return matrixData.scenarios.filter((s) => {
      if (matrixFilterCoverage !== "All") {
        if (!s.coverage_type_name.toLowerCase().includes(matrixFilterCoverage.toLowerCase())) {
          return false;
        }
      }
      if (matrixSearch.trim()) {
        const q = matrixSearch.toLowerCase();
        const inScenario =
          s.scenario_name.toLowerCase().includes(q) || s.product_name.toLowerCase().includes(q);
        const inDefaults = s.defaults.some(
          (d) => d.label.toLowerCase().includes(q) || d.display_value.toLowerCase().includes(q)
        );
        const inAddons = s.addons.some(
          (a) => a.label.toLowerCase().includes(q) || a.display_value.toLowerCase().includes(q)
        );
        const inBundles = s.bundles.some((b) => b.name.toLowerCase().includes(q));
        if (!inScenario && !inDefaults && !inAddons && !inBundles) return false;
      }
      return true;
    });
  }, [matrixData, matrixFilterCoverage, matrixSearch]);

  return (
    <div className="space-y-6">
      {/* Header & Stats Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-5 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">
              {matrixData?.company.name || "Insurance Company"} — Benefits & Packages Matrix
            </h2>
            <Badge variant="default">Underwriting Source of Truth</Badge>
          </div>
          <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
            Total comprehensive matrix view of all packages, included defaults (Cost: 0 RM), add-on riders, and bundled plan options for this company.
          </p>
        </div>

        {/* Action Buttons: Export DOCX, Export XLSX, AI Seed Spec */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={downloadDocx}
            icon={<FileDoc size={15} weight="fill" className="text-blue-600" />}
            title="Download standard Word catalog formatted like canonical policy catalogs"
          >
            Download Word (.docx)
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={downloadXlsx}
            icon={<FileXls size={15} weight="fill" className="text-emerald-600" />}
            title="Download Excel spreadsheet with summary and detailed offering sheets"
          >
            Download Excel (.xlsx)
          </Button>
          <Button
            size="sm"
            onClick={() => document.getElementById("global-ai-copilot-trigger")?.click()}
            icon={<Sparkle size={15} weight="fill" className="text-amber-500" />}
            className="bg-[var(--rl-black)] text-white hover:bg-[#2d2d2d] text-xs font-semibold"
          >
            AI Catalog Copilot
          </Button>
        </div>
      </div>

      {/* Stats Badges & Filter Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-3">
        {/* Coverage Filter Pills */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)] mr-1">
            Coverage:
          </span>
          {["All", "Comprehensive", "Third Party, Fire & Theft", "Third Party"].map((cov) => {
            const active = matrixFilterCoverage === cov;
            return (
              <button
                key={cov}
                onClick={() => setMatrixFilterCoverage(cov)}
                className={`rounded-[var(--rl-radius-sm)] px-2.5 py-1 transition-all ${
                  active
                    ? "bg-[var(--rl-black)] text-white shadow-sm"
                    : "border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                }`}
              >
                {cov === "Third Party, Fire & Theft" ? "TPFT" : cov}
              </button>
            );
          })}
        </div>

        {/* Search Bar & Counter */}
        <div className="flex items-center gap-3">
          <div className="relative w-64">
            <MagnifyingGlass
              size={14}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]"
            />
            <Input
              type="text"
              value={matrixSearch}
              onChange={(e: React.ChangeEvent<HTMLInputElement>) => setMatrixSearch(e.target.value)}
              placeholder="Search package, default or rider..."
              className="pl-8 text-xs h-8"
            />
            {matrixSearch && (
              <button
                onClick={() => setMatrixSearch("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              >
                <X size={12} />
              </button>
            )}
          </div>
          <span className="text-xs font-semibold text-[var(--rl-text-muted)]">
            {filteredMatrixScenarios.length} Scenarios
          </span>
        </div>
      </div>

      {/* Matrix Loading State */}
      {matrixLoading ? (
        <div className="py-12">
          <PageLoading />
        </div>
      ) : filteredMatrixScenarios.length === 0 ? (
        <div className="rounded-[var(--rl-radius)] border border-dashed border-[var(--rl-border)] bg-[var(--rl-surface)] p-8 text-center text-xs text-[var(--rl-text-muted)]">
          No policy scenarios found matching your filters.
        </div>
      ) : (
        /* The Comprehensive Matrix Table */
        <Card className="overflow-hidden border border-[var(--rl-border)] shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1040px] text-xs">
              <thead>
                <tr className="border-b border-[var(--rl-border)] bg-[#1F2937] text-white">
                  <th className="w-[24%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Product & Policy Scenario
                  </th>
                  <th className="w-[36%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Default Benefits (Included — Cost: 0 RM)
                  </th>
                  <th className="w-[30%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Add-on Benefits & Exact Base Cost
                  </th>
                  <th className="w-[10%] px-4 py-3 text-left text-[11px] font-bold uppercase tracking-wider">
                    Bundled Add-ons
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--rl-border)]/70 bg-[var(--rl-surface)]">
                {filteredMatrixScenarios.map((s) => {
                  const covBadgeVariant = s.coverage_type_key.includes("comp")
                    ? "success"
                    : s.coverage_type_key.includes("fire") || s.coverage_type_key.includes("tpft")
                    ? "warning"
                    : "default";

                  return (
                    <tr key={s.catalog_id} className="hover:bg-[var(--rl-bg)]/40 transition-colors">
                      {/* Col 1: Product / Scenario */}
                      <td className="px-4 py-3.5 align-top">
                        <div className="space-y-1.5">
                          <div className="font-bold text-[13px] text-[var(--rl-text-strong)] leading-snug">
                            {s.scenario_name}
                          </div>
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Badge variant={covBadgeVariant}>{s.coverage_type_name}</Badge>
                            <span className="rounded bg-[var(--rl-bg)] border border-[var(--rl-border)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--rl-text-muted)]">
                              {s.system_type}
                            </span>
                          </div>
                          <div className="text-[11px] text-[var(--rl-text-muted)] space-y-0.5 pt-1">
                            <div>
                              • <span className="font-medium text-[var(--rl-text-strong)]">Segment:</span>{" "}
                              {s.segment_name}
                            </div>
                            <div>
                              • <span className="font-medium text-[var(--rl-text-strong)]">Vehicle:</span>{" "}
                              {s.vehicle_category_name}
                            </div>
                            <div>
                              • <span className="font-medium text-[var(--rl-text-strong)]">Revision:</span> rev{" "}
                              {s.revision_number} ({s.state})
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Col 2: Defaults */}
                      <td className="px-4 py-3.5 align-top">
                        {s.defaults.length === 0 ? (
                          <span className="text-[var(--rl-text-muted)] italic text-[11px]">
                            No default benefits configured.
                          </span>
                        ) : (
                          <div className="space-y-2">
                            <div className="flex items-center gap-1.5 text-[10px] font-bold text-emerald-800 uppercase tracking-wider">
                              <ShieldCheck size={13} weight="fill" />
                              <span>{s.defaults.length} Included Benefits</span>
                            </div>
                            <div className="grid grid-cols-1 gap-1.5">
                              {s.defaults.map((d) => {
                                const isEditingLimit =
                                  editingMatrixItem?.catalog_id === s.catalog_id &&
                                  editingMatrixItem?.offering_id === d.offering_id &&
                                  editingMatrixItem?.field === "display_value";
                                const isEditingDesc =
                                  editingMatrixItem?.catalog_id === s.catalog_id &&
                                  editingMatrixItem?.offering_id === d.offering_id &&
                                  editingMatrixItem?.field === "description";

                                return (
                                  <div
                                    key={d.offering_id}
                                    className="rounded border border-emerald-200/80 bg-emerald-50/50 p-2 text-emerald-950 transition-colors"
                                  >
                                    <div className="flex items-center justify-between gap-1">
                                      <span className="font-bold text-[12px] text-emerald-950 leading-tight">
                                        {d.label}
                                      </span>
                                      <span className="shrink-0 rounded bg-emerald-600 px-1.5 py-0.5 text-[9px] font-bold uppercase text-white">
                                        0 RM
                                      </span>
                                    </div>

                                    {/* Limit Display / Inline Edit */}
                                    {isEditingLimit ? (
                                      <div className="mt-1 flex items-center gap-1">
                                        <Input
                                          autoFocus
                                          value={editingMatrixItem.value}
                                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                                            setEditingMatrixItem({
                                              ...editingMatrixItem,
                                              value: e.target.value,
                                            })
                                          }
                                          onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                                            if (e.key === "Enter") void saveMatrixInlineEdit();
                                            if (e.key === "Escape") setEditingMatrixItem(null);
                                          }}
                                          className="h-6 text-[11px] px-1.5 py-0 bg-white font-semibold text-emerald-900 border-emerald-300"
                                          placeholder="e.g. 200 km"
                                        />
                                        <button
                                          type="button"
                                          onClick={() => void saveMatrixInlineEdit()}
                                          className="p-1 rounded bg-emerald-600 text-white hover:bg-emerald-700 text-[10px]"
                                          title="Save (Enter)"
                                        >
                                          <Check size={11} weight="bold" />
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => setEditingMatrixItem(null)}
                                          className="p-1 rounded bg-gray-200 text-gray-700 hover:bg-gray-300 text-[10px]"
                                          title="Cancel (Esc)"
                                        >
                                          <X size={11} />
                                        </button>
                                      </div>
                                    ) : (
                                      <div
                                        onClick={() =>
                                          setEditingMatrixItem({
                                            catalog_id: s.catalog_id,
                                            offering_id: d.offering_id,
                                            field: "display_value",
                                            value: d.display_value || "",
                                          })
                                        }
                                        className="group/limit mt-0.5 font-semibold text-[11px] text-emerald-900 flex items-center gap-1 cursor-pointer hover:underline"
                                        title="Click to edit limit"
                                      >
                                        <span>Limit: {d.display_value || "None (Click to set)"}</span>
                                        <PencilSimple
                                          size={11}
                                          className="opacity-0 group-hover/limit:opacity-100 text-emerald-700"
                                        />
                                      </div>
                                    )}

                                    {/* Description Display / Inline Edit */}
                                    {isEditingDesc ? (
                                      <div className="mt-1 space-y-1">
                                        <textarea
                                          autoFocus
                                          rows={2}
                                          value={editingMatrixItem.value}
                                          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                                            setEditingMatrixItem({
                                              ...editingMatrixItem,
                                              value: e.target.value,
                                            })
                                          }
                                          onKeyDown={(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
                                            if (e.key === "Enter" && (e.ctrlKey || e.metaKey))
                                              void saveMatrixInlineEdit();
                                            if (e.key === "Escape") setEditingMatrixItem(null);
                                          }}
                                          className="w-full text-[10.5px] p-1.5 bg-white rounded border border-emerald-300 text-emerald-950 resize-none font-sans"
                                          placeholder="Override description for this catalog..."
                                        />
                                        <div className="flex justify-end gap-1">
                                          <button
                                            type="button"
                                            onClick={() => setEditingMatrixItem(null)}
                                            className="px-2 py-0.5 rounded bg-gray-200 text-gray-700 hover:bg-gray-300 text-[10px]"
                                          >
                                            Cancel
                                          </button>
                                          <button
                                            type="button"
                                            onClick={() => void saveMatrixInlineEdit()}
                                            className="px-2 py-0.5 rounded bg-emerald-600 text-white hover:bg-emerald-700 text-[10px] font-bold"
                                          >
                                            Save
                                          </button>
                                        </div>
                                      </div>
                                    ) : (
                                      <div
                                        onClick={() =>
                                          setEditingMatrixItem({
                                            catalog_id: s.catalog_id,
                                            offering_id: d.offering_id,
                                            field: "description",
                                            value: d.description || "",
                                          })
                                        }
                                        className="group/desc mt-0.5 text-[10.5px] text-emerald-800/90 leading-tight flex items-start gap-1 cursor-pointer hover:bg-emerald-100/50 rounded px-1 py-0.5 transition-colors"
                                        title="Click to edit description"
                                      >
                                        <span className="flex-1">
                                          {d.description || "Included in base policy"}
                                        </span>
                                        <PencilSimple
                                          size={11}
                                          className="opacity-0 group-hover/desc:opacity-100 text-emerald-700 shrink-0 mt-0.5"
                                        />
                                        {d.is_custom_description && (
                                          <span className="shrink-0 rounded bg-emerald-200 text-emerald-900 px-1 py-0.2 text-[8.5px] font-bold uppercase">
                                            Custom
                                          </span>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </td>

                      {/* Col 3: Addons */}
                      <td className="px-4 py-3.5 align-top">
                        {s.addons.length === 0 ? (
                          <span className="text-[var(--rl-text-muted)] italic text-[11px]">
                            No optional riders configured.
                          </span>
                        ) : (
                          <div className="space-y-2">
                            <div className="flex items-center gap-1.5 text-[10px] font-bold text-blue-800 uppercase tracking-wider">
                              <Plus size={13} weight="bold" />
                              <span>{s.addons.length} Optional Riders</span>
                            </div>
                            <div className="grid grid-cols-1 gap-1.5">
                              {s.addons.map((a) => {
                                const isEditingLimit =
                                  editingMatrixItem?.catalog_id === s.catalog_id &&
                                  editingMatrixItem?.offering_id === a.offering_id &&
                                  editingMatrixItem?.field === "display_value";
                                const isEditingDesc =
                                  editingMatrixItem?.catalog_id === s.catalog_id &&
                                  editingMatrixItem?.offering_id === a.offering_id &&
                                  editingMatrixItem?.field === "description";

                                return (
                                  <div
                                    key={a.offering_id}
                                    className="rounded border border-blue-200/80 bg-blue-50/50 p-2 text-blue-950 transition-colors"
                                  >
                                    <div className="flex items-center justify-between gap-1">
                                      <span className="font-bold text-[12px] text-blue-950 leading-tight">
                                        {a.label}
                                      </span>
                                      <span className="shrink-0 rounded bg-blue-600 px-1.5 py-0.5 text-[9px] font-bold text-white">
                                        {a.price_text}
                                      </span>
                                    </div>

                                    {/* Limit Display / Inline Edit */}
                                    {isEditingLimit ? (
                                      <div className="mt-1 flex items-center gap-1">
                                        <Input
                                          autoFocus
                                          value={editingMatrixItem.value}
                                          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
                                            setEditingMatrixItem({
                                              ...editingMatrixItem,
                                              value: e.target.value,
                                            })
                                          }
                                          onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
                                            if (e.key === "Enter") void saveMatrixInlineEdit();
                                            if (e.key === "Escape") setEditingMatrixItem(null);
                                          }}
                                          className="h-6 text-[11px] px-1.5 py-0 bg-white font-semibold text-blue-900 border-blue-300"
                                          placeholder="e.g. RM 500"
                                        />
                                        <button
                                          type="button"
                                          onClick={() => void saveMatrixInlineEdit()}
                                          className="p-1 rounded bg-blue-600 text-white hover:bg-blue-700 text-[10px]"
                                          title="Save (Enter)"
                                        >
                                          <Check size={11} weight="bold" />
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => setEditingMatrixItem(null)}
                                          className="p-1 rounded bg-gray-200 text-gray-700 hover:bg-gray-300 text-[10px]"
                                          title="Cancel (Esc)"
                                        >
                                          <X size={11} />
                                        </button>
                                      </div>
                                    ) : (
                                      <div
                                        onClick={() =>
                                          setEditingMatrixItem({
                                            catalog_id: s.catalog_id,
                                            offering_id: a.offering_id,
                                            field: "display_value",
                                            value: a.display_value || "",
                                          })
                                        }
                                        className="group/limit mt-0.5 font-semibold text-[11px] text-blue-900 flex items-center gap-1 cursor-pointer hover:underline"
                                        title="Click to edit limit"
                                      >
                                        <span>Limit: {a.display_value || "None (Click to set)"}</span>
                                        <PencilSimple
                                          size={11}
                                          className="opacity-0 group-hover/limit:opacity-100 text-blue-700"
                                        />
                                      </div>
                                    )}

                                    {/* Description Display / Inline Edit */}
                                    {isEditingDesc ? (
                                      <div className="mt-1 space-y-1">
                                        <textarea
                                          autoFocus
                                          rows={2}
                                          value={editingMatrixItem.value}
                                          onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) =>
                                            setEditingMatrixItem({
                                              ...editingMatrixItem,
                                              value: e.target.value,
                                            })
                                          }
                                          onKeyDown={(e: React.KeyboardEvent<HTMLTextAreaElement>) => {
                                            if (e.key === "Enter" && (e.ctrlKey || e.metaKey))
                                              void saveMatrixInlineEdit();
                                            if (e.key === "Escape") setEditingMatrixItem(null);
                                          }}
                                          className="w-full text-[10.5px] p-1.5 bg-white rounded border border-blue-300 text-blue-950 resize-none font-sans"
                                          placeholder="Override description for this catalog..."
                                        />
                                        <div className="flex justify-end gap-1">
                                          <button
                                            type="button"
                                            onClick={() => setEditingMatrixItem(null)}
                                            className="px-2 py-0.5 rounded bg-gray-200 text-gray-700 hover:bg-gray-300 text-[10px]"
                                          >
                                            Cancel
                                          </button>
                                          <button
                                            type="button"
                                            onClick={() => void saveMatrixInlineEdit()}
                                            className="px-2 py-0.5 rounded bg-blue-600 text-white hover:bg-blue-700 text-[10px] font-bold"
                                          >
                                            Save
                                          </button>
                                        </div>
                                      </div>
                                    ) : (
                                      <div
                                        onClick={() =>
                                          setEditingMatrixItem({
                                            catalog_id: s.catalog_id,
                                            offering_id: a.offering_id,
                                            field: "description",
                                            value: a.description || "",
                                          })
                                        }
                                        className="group/desc mt-0.5 text-[10.5px] text-blue-800/90 leading-tight flex items-start gap-1 cursor-pointer hover:bg-blue-100/50 rounded px-1 py-0.5 transition-colors"
                                        title="Click to edit description"
                                      >
                                        <span className="flex-1">
                                          {a.description || "Optional payable endorsement"}
                                        </span>
                                        <PencilSimple
                                          size={11}
                                          className="opacity-0 group-hover/desc:opacity-100 text-blue-700 shrink-0 mt-0.5"
                                        />
                                        {a.is_custom_description && (
                                          <span className="shrink-0 rounded bg-blue-200 text-blue-900 px-1 py-0.2 text-[8.5px] font-bold uppercase">
                                            Custom
                                          </span>
                                        )}
                                      </div>
                                    )}
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </td>

                      {/* Col 4: Bundles */}
                      <td className="px-4 py-3.5 align-top">
                        {s.bundles.length === 0 ? (
                          <span className="text-[var(--rl-text-muted)] italic text-[11px]">None</span>
                        ) : (
                          <div className="space-y-2">
                            {s.bundles.map((b) => (
                              <div
                                key={b.package_id}
                                className="rounded border border-purple-200 bg-purple-50/60 p-2 text-purple-950"
                              >
                                <div className="font-bold text-[11px] text-purple-950">{b.name}</div>
                                {b.plans.length > 0 && (
                                  <div className="mt-1 space-y-0.5">
                                    {b.plans.map((p) => (
                                      <div
                                        key={p.plan_id}
                                        className="text-[10px] font-medium text-purple-800"
                                      >
                                        • {p.name}
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
