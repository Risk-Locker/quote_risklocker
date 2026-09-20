"use client";

import { useState, useTransition } from "react";
import {
  X,
  Lightning,
  ArrowsClockwise,
  CheckCircle,
  WarningCircle,
  ShieldCheck,
  Check,
  Tag,
  Car,
  PencilSimple,
  Plus,
  Trash,
  GitBranch,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { NeuralCubeIcon } from "@/components/ui/neural-cube-icon";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import type { CatalogSummary as Catalog, CompanySummary as Company } from "@/types/benefits";

type OperationPreviewItem = {
  catalog_id: string;
  catalog_name: string;
  action: "update_plan_item" | "add_offering" | "remove_offering" | "update_description";
  concept_key: string;
  concept_label: string;
  current_value?: string | null;
  new_value?: string | null;
  current_description?: string | null;
  new_description?: string | null;
  details?: string | null;
};

type PreviewResponse = {
  parsed_intent: {
    intent: string;
    target_company?: string | null;
    operations: Record<string, unknown>[];
    notes?: string | null;
  };
  company_id: string;
  matched_catalogs: Array<{
    id: string;
    name: string;
    vehicle_category?: string | null;
    engine_type?: string | null;
  }>;
  operations_preview: OperationPreviewItem[];
  profile_versioning_recommended: boolean;
  active_profile_id?: string | null;
  active_profile_version?: string | null;
  suggested_next_version?: string | null;
};

type ApplyResponse = {
  applied_count: number;
  catalogs_updated: string[];
  new_profile?: {
    id: string;
    version: string;
    is_active: boolean;
  } | null;
  message: string;
};

interface AiCatalogSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  companies: Company[];
  selectedCompanyId: string;
  onCompanyChange: (companyId: string) => void;
  catalogs: Catalog[];
  onOperationsApplied?: () => void | Promise<void>;
}

const EXAMPLE_PROMPTS = [
  "Change AmAssurance towing tier 1 to 200km and tier 2 to 300km",
  "Add windscreen RM 500 as addon for all ICE saloon cars",
  "Update QBE main benefit description to 'Comprehensive roadside assistance with unlimited towing'",
  "Set towing to 100 km for private cars",
];

export function AiCatalogSidebar({
  isOpen,
  onClose,
  companies,
  selectedCompanyId,
  onCompanyChange,
  catalogs,
  onOperationsApplied,
}: AiCatalogSidebarProps) {
  const [query, setQuery] = useState("");
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Preview result state
  const [previewData, setPreviewData] = useState<PreviewResponse | null>(null);
  const [selectedOperationIndices, setSelectedOperationIndices] = useState<Set<number>>(new Set());

  // Versioning state
  const [createNewVersion, setCreateNewVersion] = useState(true);
  const [customVersionName, setCustomVersionName] = useState("");
  const [activateProfile, setActivateProfile] = useState(true);
  const [publishCatalogs, setPublishCatalogs] = useState(false);

  const activeCompany = companies.find((c) => c.id === selectedCompanyId);

  // Request preview
  async function handlePreview() {
    if (!query.trim()) {
      setError("Please describe the catalog or benefit changes you want to make.");
      return;
    }
    if (!selectedCompanyId) {
      setError("Please select an insurance company first.");
      return;
    }

    setLoadingPreview(true);
    setError(null);
    setSuccess(null);
    setPreviewData(null);

    try {
      const res = await api<PreviewResponse>(
        `/business/companies/${selectedCompanyId}/catalog-operations/preview`,
        {
          method: "POST",
          body: JSON.stringify({
            query: query.trim(),
          }),
        }
      );

      setPreviewData(res);
      // Select all operations by default
      const allIndices = new Set<number>();
      res.operations_preview.forEach((_, idx) => allIndices.add(idx));
      setSelectedOperationIndices(allIndices);

      if (res.suggested_next_version) {
        setCustomVersionName(res.suggested_next_version);
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoadingPreview(false);
    }
  }

  // Toggle individual operation
  function toggleOperation(index: number) {
    const next = new Set(selectedOperationIndices);
    if (next.has(index)) {
      next.delete(index);
    } else {
      next.add(index);
    }
    setSelectedOperationIndices(next);
  }

  // Toggle all
  function toggleAll() {
    if (!previewData) return;
    if (selectedOperationIndices.size === previewData.operations_preview.length) {
      setSelectedOperationIndices(new Set());
    } else {
      const all = new Set<number>();
      previewData.operations_preview.forEach((_, idx) => all.add(idx));
      setSelectedOperationIndices(all);
    }
  }

  // Apply selected operations
  async function handleApply() {
    if (!previewData || selectedOperationIndices.size === 0) {
      setError("Please select at least one operation to apply.");
      return;
    }

    const opsToApply = previewData.parsed_intent.operations;

    setApplying(true);
    setError(null);
    setSuccess(null);

    try {
      const res = await api<ApplyResponse>(
        `/business/companies/${selectedCompanyId}/catalog-operations/apply`,
        {
          method: "POST",
          body: JSON.stringify({
            operations: opsToApply,
            create_new_profile_version: createNewVersion,
            new_version_name: customVersionName.trim() || undefined,
            activate_profile: activateProfile,
            publish_catalogs: publishCatalogs,
          }),
        }
      );

      setSuccess(
        `${res.message} ${
          res.new_profile
            ? `Active Unified Profile is now ${res.new_profile.version}.`
            : ""
        }`
      );
      setPreviewData(null);
      setQuery("");

      if (onOperationsApplied) {
        await onOperationsApplied();
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setApplying(false);
    }
  }

  if (!isOpen) return null;

  return (
    <aside
      aria-label="AI Catalog Copilot Sidebar"
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-[480px] flex-col border-l border-[var(--rl-border)] bg-white shadow-2xl transition-transform duration-200 ease-in-out sm:w-[480px]"
    >
      {/* Sidebar Header */}
      <div className="flex items-center justify-between border-b border-[var(--rl-border)] bg-[var(--rl-surface)] px-5 py-3.5">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-[var(--rl-radius-sm)] bg-[var(--rl-black)] text-white shadow-xs">
            <NeuralCubeIcon size={18} accentCore={true} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold tracking-tight text-[var(--rl-text-strong)]">AI Catalog Copilot</h2>
              <Badge variant="default" className="text-[10px] py-0 px-1.5 font-semibold">
                Multi-Catalog Engine
              </Badge>
            </div>
            <p className="text-[11px] text-[var(--rl-text-muted)] mt-0.5">
              Bulk natural language edits &amp; profile versioning
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-[var(--rl-radius-sm)] p-1.5 text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)] hover:text-[var(--rl-text-strong)] transition-colors"
          aria-label="Close AI Sidebar"
        >
          <X size={18} weight="bold" />
        </button>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-5 space-y-5">
        {/* Target Insurer Picker */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-[var(--rl-text-strong)] flex items-center justify-between">
            <span>Target Insurance Company</span>
            {activeCompany ? (
              <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">
                {catalogs.filter((c) => c.company_id === activeCompany.id).length} catalog(s) loaded
              </span>
            ) : null}
          </label>
          <Select
            value={selectedCompanyId}
            onChange={(e) => onCompanyChange(e.target.value)}
            className="text-xs font-medium bg-[var(--rl-surface)] border-[var(--rl-border)] text-[var(--rl-text-strong)] rounded-[var(--rl-radius-sm)]"
          >
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} {c.status === "inactive" ? "(Inactive)" : ""}
              </option>
            ))}
          </Select>
        </div>

        {/* Prompt Input & Examples */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-[var(--rl-text-strong)] flex items-center gap-1.5">
            <Lightning size={14} weight="fill" className="text-amber-600" />
            <span>Natural Language Instruction</span>
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. Change AmAssurance towing tier 1 to 200km and tier 2 to 300km..."
            rows={3}
            className="w-full resize-none rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-3 text-xs leading-relaxed focus:border-[var(--rl-black)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)] placeholder:text-[var(--rl-text-muted)] text-[var(--rl-text-strong)] font-sans"
          />

          {/* Quick Prompt Chips */}
          <div className="space-y-1">
            <p className="text-[11px] font-semibold text-[var(--rl-text-muted)]">Quick Examples:</p>
            <div className="flex flex-wrap gap-1.5">
              {EXAMPLE_PROMPTS.map((p, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setQuery(p)}
                  className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2.5 py-1 text-[11px] text-[var(--rl-text)] hover:border-[var(--rl-black)]/40 hover:bg-[var(--rl-bg)] hover:text-[var(--rl-text-strong)] transition-colors text-left truncate max-w-full active:scale-[0.98]"
                  title={p}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Error and Success Banners */}
        {error ? (
          <div className="flex items-start gap-2.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-red)]/25 bg-[var(--rl-red-light)] p-3 text-xs font-medium text-[var(--rl-red)]">
            <WarningCircle size={16} weight="fill" className="mt-0.5 flex-shrink-0 text-[var(--rl-red)]" />
            <div className="flex-1">{error}</div>
          </div>
        ) : null}

        {success ? (
          <div className="flex items-start gap-2.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-success)]/25 bg-[var(--rl-success-light)] p-3 text-xs font-medium text-[var(--rl-success)]">
            <CheckCircle size={16} weight="fill" className="mt-0.5 flex-shrink-0 text-[var(--rl-success)]" />
            <div className="flex-1">{success}</div>
          </div>
        ) : null}

        {/* Analyze / Preview Trigger */}
        <Button
          onClick={handlePreview}
          disabled={loadingPreview || !query.trim()}
          className="w-full text-white text-xs font-bold py-2.5 shadow-card hover:shadow-lift"
        >
          {loadingPreview ? (
            <span className="flex items-center gap-2">
              <ArrowsClockwise size={14} className="animate-spin" />
              Parsing Intent &amp; Computing Diffs...
            </span>
          ) : (
            <span className="flex items-center gap-2">
              <NeuralCubeIcon size={14} accentCore={true} />
              Analyze Intent &amp; Preview Operations
            </span>
          )}
        </Button>

        {/* Preview Results & Confirmation Section */}
        {previewData ? (
          <div className="space-y-4 rounded-xl border border-gray-200 bg-gray-50/70 p-4">
            <div className="flex items-center justify-between border-b border-gray-200 pb-2.5">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-gray-700">
                  Proposed Operations ({previewData.operations_preview.length})
                </h3>
                <p className="text-[11px] text-gray-500">
                  Matched across {previewData.matched_catalogs.length} catalog(s)
                </p>
              </div>
              <button
                type="button"
                onClick={toggleAll}
                className="text-[11px] font-semibold text-[var(--rl-red)] hover:underline"
              >
                {selectedOperationIndices.size === previewData.operations_preview.length
                  ? "Deselect All"
                  : "Select All"}
              </button>
            </div>

            {/* Operations List */}
            {previewData.operations_preview.length === 0 ? (
              <p className="text-xs text-gray-500 italic text-center py-3">
                No matching catalogs or concepts found for this request. Please clarify the instruction.
              </p>
            ) : (
              <div className="space-y-2.5 max-h-[280px] overflow-y-auto pr-1">
                {previewData.operations_preview.map((op, idx) => {
                  const isChecked = selectedOperationIndices.has(idx);
                  return (
                    <div
                      key={idx}
                      onClick={() => toggleOperation(idx)}
                      className={`cursor-pointer rounded-lg border p-3 transition-all ${
                        isChecked
                          ? "border-emerald-300 bg-white shadow-xs"
                          : "border-gray-200 bg-gray-100/60 opacity-60"
                      }`}
                    >
                      <div className="flex items-start gap-2.5">
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleOperation(idx)}
                          className="mt-0.5 rounded border-gray-300 text-[var(--rl-red)] focus:ring-[var(--rl-red)]"
                        />
                        <div className="flex-1 min-w-0 space-y-1">
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="font-semibold text-xs text-[var(--rl-text-strong)]">
                              {op.concept_label}
                            </span>
                            <Badge
                              variant={
                                op.action === "update_plan_item"
                                  ? "warning"
                                  : op.action === "add_offering"
                                  ? "success"
                                  : op.action === "remove_offering"
                                  ? "danger"
                                  : "default"
                              }
                              className="text-[10px] px-1.5 py-0 font-bold"
                            >
                              {op.action === "update_plan_item"
                                ? "UPDATE TIER"
                                : op.action === "add_offering"
                                ? "ADD OFFERING"
                                : op.action === "remove_offering"
                                ? "REMOVE"
                                : "EDIT DESC"}
                            </Badge>
                          </div>

                          <p className="text-[11px] text-gray-500 truncate font-mono">
                            Catalog: {op.catalog_name}
                          </p>

                          {/* Value Diff */}
                          {op.new_value !== undefined ? (
                            <div className="flex items-center gap-2 text-xs pt-1">
                              {op.current_value ? (
                                <span className="line-through text-gray-400 font-mono">
                                  {op.current_value}
                                </span>
                              ) : null}
                              <span className="font-bold text-emerald-700 font-mono">
                                → {op.new_value}
                              </span>
                            </div>
                          ) : null}

                          {/* Description Diff */}
                          {op.new_description ? (
                            <div className="text-[11px] text-gray-600 bg-gray-50 p-2 rounded border border-gray-100 mt-1">
                              <span className="font-semibold text-gray-700">New Description: </span>
                              “{op.new_description}”
                            </div>
                          ) : null}

                          {op.details ? (
                            <p className="text-[10px] text-gray-400 italic">{op.details}</p>
                          ) : null}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Profile Versioning Controls */}
            <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3.5 space-y-3">
              <div className="flex items-center gap-2">
                <GitBranch size={16} weight="bold" className="text-[var(--rl-text-strong)]" />
                <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                  Profile Versioning &amp; Immutability
                </span>
              </div>

              <div className="space-y-2">
                <label className="flex items-start gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={createNewVersion}
                    onChange={(e) => setCreateNewVersion(e.target.checked)}
                    className="mt-0.5 rounded-[3px] border-[var(--rl-border)] text-[var(--rl-black)] accent-[var(--rl-black)] focus:ring-[var(--rl-black)]"
                  />
                  <div className="text-[11px] text-[var(--rl-text-strong)]">
                    <strong className="block font-semibold">
                      Clone &amp; create new profile version
                    </strong>
                    <span className="text-[var(--rl-text-muted)]">
                      Keeps historical quotations safe by cloning from active profile (
                      {previewData.active_profile_version || "v2"})
                    </span>
                  </div>
                </label>

                {createNewVersion ? (
                  <div className="pl-6 pt-1">
                    <label className="text-[11px] font-semibold text-[var(--rl-text-strong)] block mb-1">
                      New Version Name:
                    </label>
                    <Input
                      value={customVersionName}
                      onChange={(e) => setCustomVersionName(e.target.value)}
                      placeholder="e.g. v3 or v3-towing-updates"
                      className="text-xs h-8 bg-white border-[var(--rl-border)] font-mono"
                    />
                  </div>
                ) : null}

                <label className="flex items-center gap-2 cursor-pointer pl-6">
                  <input
                    type="checkbox"
                    checked={activateProfile}
                    onChange={(e) => setActivateProfile(e.target.checked)}
                    className="rounded-[3px] border-[var(--rl-border)] text-[var(--rl-black)] accent-[var(--rl-black)] focus:ring-[var(--rl-black)]"
                  />
                  <span className="text-[11px] text-[var(--rl-text-strong)] font-medium">
                    Set as active unified benefit profile immediately
                  </span>
                </label>
              </div>
            </div>

            {/* Final Apply Button */}
            <Button
              onClick={handleApply}
              disabled={applying || selectedOperationIndices.size === 0}
              className="w-full text-white text-xs font-bold py-2.5 shadow-card hover:shadow-lift"
            >
              {applying ? (
                <span className="flex items-center gap-2">
                  <ArrowsClockwise size={14} className="animate-spin" />
                  Applying Changes &amp; Updating Catalogs...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <Check size={14} weight="bold" />
                  Confirm &amp; Apply {selectedOperationIndices.size} Operation(s)
                </span>
              )}
            </Button>
          </div>
        ) : null}
      </div>
    </aside>
  );
}
