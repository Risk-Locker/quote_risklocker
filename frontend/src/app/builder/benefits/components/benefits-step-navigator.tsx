"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import {
  Buildings,
  CheckCircle,
  Copy,
  Info,
  Lightning,
  ShieldCheck,
  Table,
  Trash,
  TreeStructure,
} from "@phosphor-icons/react";
import type {
  CompanySummary as Company,
  BenefitProfile,
  CompanyBenefitConfig,
  CompanyBenefitCondition,
  CompanyWorkspaceData as CompanyWorkspace,
  HierarchyItem,
} from "@/types/benefits";

export interface BenefitsStepNavigatorProps {
  companies: Company[];
  selectedCompanyId: string;
  selectedCompany: Company | null;
  companyWorkspace: CompanyWorkspace | null;
  loadCompany: (id: string) => Promise<unknown>;
  profiles: BenefitProfile[];
  profilesLoading: boolean;
  selectedProfileId: string;
  setSelectedProfileId: (id: string) => void;
  selectedProfile: BenefitProfile | null;
  companyConfigs: CompanyBenefitConfig[];
  companyConditions: CompanyBenefitCondition[];
  loadCompanyConfigs: (companyId: string, profileId?: string) => Promise<unknown>;
  loadCompanyConditions: (companyId: string, profileId?: string) => Promise<unknown>;
  profileActionLoading: boolean;
  handleActivateProfile: (id: string) => void;
  handleDeleteDraftProfile: (id: string) => void;
  setCloneName: (val: string) => void;
  setCloneNotes: (val: string) => void;
  setCloneModalOpen: (open: boolean) => void;
  screenTab: "company_benefits" | "catalogs" | "conditions" | "matrix";
  segments: HierarchyItem[];
  selectedSegmentId: string;
  setSelectedSegmentId: (id: string) => void;
  selectedEngineType: "ice" | "ev";
  setSelectedEngineType: (type: "ice" | "ev") => void;
  vehicles: HierarchyItem[];
  selectedVehicleId: string;
  setSelectedVehicleId: (id: string) => void;
  builderCoverageFilter: "comprehensive" | "tpft" | "tpo";
  setBuilderCoverageFilter: (filter: "comprehensive" | "tpft" | "tpo") => void;
  productConfigs: Array<{
    id: string;
    package?: { name: string } | null;
    [key: string]: any;
  }>;
  selectedCatalogId: string;
  loadCatalog: (id: string) => Promise<unknown>;
  fileUrl: (path?: string | null) => string;
}

export function BenefitsStepNavigator({
  companies,
  selectedCompanyId,
  companyWorkspace,
  loadCompany,
  profiles,
  profilesLoading,
  selectedProfileId,
  setSelectedProfileId,
  selectedProfile,
  companyConfigs,
  companyConditions,
  loadCompanyConfigs,
  loadCompanyConditions,
  profileActionLoading,
  handleActivateProfile,
  handleDeleteDraftProfile,
  setCloneName,
  setCloneNotes,
  setCloneModalOpen,
  screenTab,
  segments,
  selectedSegmentId,
  setSelectedSegmentId,
  selectedEngineType,
  setSelectedEngineType,
  vehicles,
  selectedVehicleId,
  setSelectedVehicleId,
  builderCoverageFilter,
  setBuilderCoverageFilter,
  productConfigs,
  selectedCatalogId,
  loadCatalog,
  fileUrl,
}: BenefitsStepNavigatorProps) {
  return (
    <div className="mt-4 rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-3.5 space-y-3.5">
      {/* Row 1: Insurance companies (Full-width, scalable for many companies) */}
      <div className="rl-tour-companies flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
            1. Insurance companies ({companies.length})
          </span>
          <span className="text-[11px] text-[var(--rl-text-muted)]">
            Click an insurer to manage products & policy benefits
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {companies.map((c) => {
            const active = c.id === selectedCompanyId;
            const isPkgSystem = Boolean(
              companyWorkspace?.catalogs?.some((cat: any) => cat.company_id === c.id && cat.package_id)
            );
            return (
              <button
                key={c.id}
                onClick={() => loadCompany(c.id)}
                className={`flex items-center gap-2.5 rounded-[var(--rl-radius-sm)] px-3.5 py-2 text-left font-medium transition-all ${
                  active
                    ? "bg-[var(--rl-black)] text-white shadow-sm"
                    : "border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                }`}
              >
                {c.logo?.url ? (
                  <img
                    src={fileUrl(c.logo.url)}
                    alt={c.name}
                    loading="lazy"
                    className="h-4 w-4 rounded-[2px] object-contain bg-white"
                  />
                ) : (
                  <Buildings size={15} className={active ? "text-white" : "text-[var(--rl-text-muted)]"} />
                )}
                <span className="text-xs font-semibold">{c.name}</span>
                <span
                  className={`rounded-[4px] px-1.5 py-0.5 text-[10px] font-semibold uppercase ${
                    active
                      ? "bg-white/20 text-white"
                      : "bg-[var(--rl-bg)] text-[var(--rl-text-muted)] border border-[var(--rl-border)]"
                  }`}
                >
                  {isPkgSystem ? "Package System" : "Add-on System"}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Row 1b: Benefit Profile Versioning & Governance Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
              Benefit Profile:
            </span>
            <Tooltip content="Versioned governance for company benefits and conditions. Inactive or disabled benefits cascade to omit from quote suggestions, review seeding, and PDF generation.">
              <Info size={13} className="text-[var(--rl-text-muted)] cursor-pointer" />
            </Tooltip>
          </div>

          {profilesLoading ? (
            <span className="text-xs text-[var(--rl-text-muted)] animate-pulse">Loading profiles...</span>
          ) : profiles.length === 0 ? (
            <span className="text-xs text-[var(--rl-text-muted)] italic">No profiles found.</span>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={selectedProfileId}
                onChange={(e) => {
                  const nextId = e.target.value;
                  setSelectedProfileId(nextId);
                  if (selectedCompanyId) {
                    loadCompanyConfigs(selectedCompanyId, nextId);
                    loadCompanyConditions(selectedCompanyId, nextId);
                  }
                }}
                className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] px-2.5 py-1 text-xs font-semibold text-[var(--rl-text-strong)] focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
              >
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    v{p.version_number}: {p.name} ({p.status.toUpperCase()})
                    {p.is_active ? " ★ Active" : ""}
                  </option>
                ))}
              </select>

              {selectedProfile && (
                <div className="flex items-center gap-1.5">
                  <span
                    className={`rounded-[4px] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                      selectedProfile.is_active
                        ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                        : selectedProfile.status === "archived"
                        ? "bg-neutral-100 text-neutral-600 border border-neutral-300"
                        : "bg-amber-100 text-amber-800 border border-amber-300"
                    }`}
                  >
                    {selectedProfile.is_active ? "Active Master" : selectedProfile.status}
                  </span>
                  <span className="text-[11px] text-[var(--rl-text-muted)] font-medium">
                    {selectedProfile.configs_count ?? companyConfigs.length} configs ·{" "}
                    {selectedProfile.conditions_count ?? companyConditions.length} rules
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {selectedProfile && !selectedProfile.is_active && (
            <>
              {selectedProfile.status === "draft" && (
                <Button
                  size="sm"
                  onClick={() => handleActivateProfile(selectedProfile.id)}
                  disabled={profileActionLoading}
                  className="gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm text-xs font-semibold h-7 px-2.5"
                  title="Make this draft profile the live active configuration"
                >
                  <CheckCircle size={13} weight="bold" />
                  <span>Activate Profile</span>
                </Button>
              )}

              <Button
                variant="secondary"
                size="sm"
                onClick={() => handleDeleteDraftProfile(selectedProfile.id)}
                disabled={profileActionLoading}
                className="gap-1 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200 text-xs h-7 px-2"
                title={`Delete this ${selectedProfile.status} profile`}
              >
                <Trash size={13} />
                <span>Delete Profile</span>
              </Button>
            </>
          )}

          {selectedProfile && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                const maxV =
                  profiles.reduce((max, p) => Math.max(max, p.version_number), 0) ||
                  selectedProfile.version_number;
                setCloneName(`${selectedProfile.name.replace(/\s*\(v\d+\)$/, "")} (v${maxV + 1})`);
                setCloneNotes(selectedProfile.notes || "");
                setCloneModalOpen(true);
              }}
              disabled={profileActionLoading}
              className="gap-1.5 text-xs h-7 px-2.5"
              title="Clone this profile into a new editable draft"
            >
              <Copy size={13} />
              <span>Clone as New Version</span>
            </Button>
          )}
        </div>
      </div>

      {screenTab === "company_benefits" ? (
        <div className="flex items-center gap-2 border-t border-[var(--rl-border)] pt-3 text-xs text-[var(--rl-text-muted)]">
          <ShieldCheck size={16} className="text-emerald-600 shrink-0" weight="fill" />
          <span>
            <strong>Insurer Master Benefit Pool:</strong> Enable or disable benefits and customize short
            descriptions for this insurer. Scenario catalogs below
            strictly inherit from this enabled set.
          </span>
        </div>
      ) : screenTab === "conditions" ? (
        <div className="flex items-center gap-2 border-t border-[var(--rl-border)] pt-3 text-xs text-[var(--rl-text-muted)]">
          <Lightning size={16} className="text-amber-500 shrink-0" weight="fill" />
          <span>
            <strong>Dynamic Condition Rules:</strong> Cross-benefit conditional upgrades for this insurer.
            Evaluates in realtime during quote calculations and PDF generation.
          </span>
        </div>
      ) : screenTab === "matrix" ? (
        <div className="flex items-center gap-2 border-t border-[var(--rl-border)] pt-3 text-xs text-[var(--rl-text-muted)]">
          <Table size={16} className="text-purple-600 shrink-0" weight="fill" />
          <span>
            <strong>Underwriting Matrix:</strong> Complete policy breakdown of default benefits, add-on riders,
            and bundled packages for this insurer.
          </span>
        </div>
      ) : (
        <>
          {/* Row 2: Segment + Engine Type + Vehicle Type + Coverage */}
          <div className="flex flex-wrap items-center gap-4 border-t border-[var(--rl-border)] pt-3 text-xs">
            {/* Step 2: Segment */}
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                  2. Segment:
                </span>
                <Tooltip content="Choose private vs commercial vehicle policy scope">
                  <Info size={11} className="text-[var(--rl-text-muted)]" />
                </Tooltip>
              </div>
              <div className="flex gap-1">
                {segments.map((seg) => {
                  const active = seg.id === selectedSegmentId;
                  return (
                    <button
                      key={seg.id}
                      onClick={() => setSelectedSegmentId(seg.id)}
                      className={`rounded-[var(--rl-radius-sm)] px-2.5 py-1 text-xs font-medium transition-all ${
                        active
                          ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] border border-[var(--rl-border)] shadow-sm font-semibold"
                          : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                      }`}
                    >
                      {seg.key === "private" ? "Private" : "Company / Commercial"}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="hidden h-5 w-px bg-[var(--rl-border)] sm:block" />

            {/* Step 3: Engine Type */}
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1">
                <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                  3. Engine:
                </span>
                <Tooltip content="Filter policy products for internal combustion (ICE) or electric vehicles (EV)">
                  <Info size={11} className="text-[var(--rl-text-muted)]" />
                </Tooltip>
              </div>
              <div className="flex gap-1">
                {(["ice", "ev"] as const).map((eng) => {
                  const active = selectedEngineType === eng;
                  return (
                    <button
                      key={eng}
                      onClick={() => setSelectedEngineType(eng)}
                      className={`flex items-center gap-1 rounded-[var(--rl-radius-sm)] px-2.5 py-1 text-xs font-medium transition-all ${
                        active
                          ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] border border-[var(--rl-border)] shadow-sm font-semibold"
                          : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                      }`}
                    >
                      {eng === "ev" && <Lightning size={12} weight="fill" className="text-amber-500" />}
                      <span>{eng === "ice" ? "ICE (Petrol/Diesel)" : "EV (Electric)"}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="hidden h-5 w-px bg-[var(--rl-border)] sm:block" />

            {/* Step 4: Vehicle Type */}
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                4. Vehicle type:
              </span>
              <div className="flex gap-1">
                {vehicles.map((v) => {
                  const active = v.id === selectedVehicleId;
                  return (
                    <button
                      key={v.id}
                      onClick={() => setSelectedVehicleId(v.id)}
                      className={`rounded-[var(--rl-radius-sm)] px-2.5 py-1 text-xs font-medium transition-all ${
                        active
                          ? "bg-[var(--rl-surface)] text-[var(--rl-text-strong)] border border-[var(--rl-border)] shadow-sm font-semibold"
                          : "text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                      }`}
                    >
                      {v.name}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="hidden h-5 w-px bg-[var(--rl-border)] sm:block" />

            {/* Step 5: Coverage Type */}
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                5. Coverage:
              </span>
              <div className="flex flex-wrap items-center gap-1.5 text-xs font-semibold">
                {[
                  { id: "comprehensive", label: "Comprehensive", hint: "(Third Party available)" },
                  { id: "tpft", label: "Third Party, Fire & Theft", hint: "" },
                  { id: "tpo", label: "Third Party", hint: "" },
                ].map((cov) => {
                  const active = builderCoverageFilter === cov.id;
                  return (
                    <button
                      key={cov.id}
                      onClick={() => builderCoverageFilter !== cov.id && setBuilderCoverageFilter(cov.id as any)}
                      className={`flex items-center gap-1.5 rounded-[var(--rl-radius-sm)] px-2.5 py-1 transition-all ${
                        active
                          ? "bg-[var(--rl-surface)] border border-[var(--rl-border)] text-[var(--rl-text-strong)] shadow-sm"
                          : "border border-transparent text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                      }`}
                    >
                      <span>{cov.label}</span>
                      {cov.hint && (
                        <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">
                          {cov.hint}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Row 3: Product / Configuration Selection */}
          <div className="rl-tour-product flex flex-wrap items-center gap-2 border-t border-[var(--rl-border)] pt-3">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
              6. Product:
            </span>

            {productConfigs.length === 0 ? (
              <span className="text-xs text-[var(--rl-text-muted)]">
                No configurations for this product yet.
              </span>
            ) : (
              productConfigs.map((config) => {
                const active = config.id === selectedCatalogId;
                const displayName = config.package ? config.package.name : "Single";
                return (
                  <button
                    key={config.id}
                    onClick={() => loadCatalog(config.id)}
                    className={`flex items-center gap-2 rounded-[var(--rl-radius-sm)] px-3 py-1.5 text-xs font-semibold transition-all ${
                      active
                        ? "bg-[var(--rl-black)] text-white shadow-sm"
                        : "border border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)]"
                    }`}
                  >
                    <TreeStructure
                      size={14}
                      className={active ? "text-white" : "text-[var(--rl-text-muted)]"}
                    />
                    <span>{displayName}</span>
                    <span
                      className={`text-[10px] font-normal ${
                        active ? "text-neutral-300" : "text-[var(--rl-text-muted)]"
                      }`}
                    >
                      {config.package ? "Package mode" : "Single mode"}
                    </span>
                  </button>
                );
              })
            )}
          </div>
        </>
      )}
    </div>
  );
}
