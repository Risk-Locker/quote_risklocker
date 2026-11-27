"use client";

import { useEffect, useState } from "react";
import { Plus, Trash } from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { BenefitCombobox } from "./benefit-combobox";
import type {
  CompanyBenefitBundle,
  CompanyBenefitBundleEffect,
  CompanyBenefitBundleTier,
  CompanySummary as Company,
  ConceptSummary as Concept,
} from "@/types/benefits";

interface BundleEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedCompany: Company | null;
  concepts: Concept[];
  editingBundle: CompanyBenefitBundle | null;
  saving: boolean;
  onSave: (payload: Omit<CompanyBenefitBundle, "id" | "company_id" | "bundle_key"> & { id?: string; bundle_key?: string }) => Promise<void>;
}

const ICON_HINT_OPTIONS = [
  { value: "", label: "Auto / Concept Default" },
  { value: "towing", label: "Standard Towing Truck" },
  { value: "unlimited_towing", label: "Unlimited Towing (∞ Recovery Truck)" },
  { value: "key_care", label: "Key Replacement" },
  { value: "pa", label: "Personal Accident" },
  { value: "special_perils", label: "Special Perils / Flood" },
  { value: "betterment", label: "Waiver of Betterment" },
  { value: "windscreen", label: "Windscreen" },
  { value: "cart", label: "CART / Daily Allowance" },
];

function emptyEffect(concepts: Concept[]): CompanyBenefitBundleEffect {
  const towing = concepts.find((c) => c.concept_key === "towing");
  return {
    target_concept_id: towing?.id || "",
    effect_type: "upgrade_to_box2",
    display_title: "Unlimited Towing Assistance",
    display_value: "",
    display_description: "24/7 unlimited emergency towing assistance nationwide.",
    icon_hint: "unlimited_towing",
    comparison_value: "Unlimited",
    sort_order: 0,
  };
}

export function BundleEditorDialog({
  open,
  onOpenChange,
  selectedCompany,
  concepts,
  editingBundle,
  saving,
  onSave,
}: BundleEditorDialogProps) {
  const [name, setName] = useState("");
  const [bundleKey, setBundleKey] = useState("");
  const [primaryConceptId, setPrimaryConceptId] = useState("");
  const [extraTriggerText, setExtraTriggerText] = useState("");
  const [keywordsText, setKeywordsText] = useState("");
  const [catalogScope, setCatalogScope] = useState("");
  const [forceBox2, setForceBox2] = useState(true);
  const [hasPlanTiers, setHasPlanTiers] = useState(false);
  const [tiers, setTiers] = useState<CompanyBenefitBundleTier[]>([]);
  const [localError, setLocalError] = useState("");

  useEffect(() => {
    if (!open) return;
    setLocalError("");
    if (editingBundle) {
      setName(editingBundle.name || "");
      setBundleKey(editingBundle.bundle_key || "");
      setPrimaryConceptId(editingBundle.primary_concept_id || "");
      const extras = (editingBundle.trigger_concept_ids || []).filter(
        (id) => id !== editingBundle.primary_concept_id
      );
      setExtraTriggerText(extras.join(", "));
      setKeywordsText((editingBundle.match_aliases || []).join(", "));
      setCatalogScope(editingBundle.catalog_scope || "");
      setForceBox2(Boolean(editingBundle.force_box2 ?? true));
      setHasPlanTiers(Boolean(editingBundle.has_plan_tiers));
      setTiers(
        editingBundle.tiers?.length
          ? editingBundle.tiers.map((t) => ({
              ...t,
              match_tokens: t.match_tokens || [],
              effects: t.effects || [],
            }))
          : [{ label: "Default", match_tokens: [], is_default_fallback: true, sort_order: 0, effects: [emptyEffect(concepts)] }]
      );
    } else {
      setName("");
      setBundleKey("");
      setPrimaryConceptId("");
      setExtraTriggerText("");
      setKeywordsText("");
      setCatalogScope("");
      setForceBox2(true);
      setHasPlanTiers(false);
      setTiers([
        {
          label: "Default",
          match_tokens: [],
          is_default_fallback: true,
          sort_order: 0,
          effects: [emptyEffect(concepts)],
        },
      ]);
    }
  }, [open, editingBundle, concepts]);

  const handleSubmit = async () => {
    if (!name.trim() || !primaryConceptId) {
      setLocalError("Bundle name and Primary Add-On Concept are required.");
      return;
    }
    if (tiers.length === 0) {
      setLocalError("Add at least one tier.");
      return;
    }
    const extraTrigIds = extraTriggerText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const matchKeywords = keywordsText
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      setLocalError("");
      await onSave({
        ...(editingBundle?.id ? { id: editingBundle.id } : {}),
        ...(bundleKey.trim() ? { bundle_key: bundleKey.trim() } : {}),
        name: name.trim(),
        primary_concept_id: primaryConceptId,
        trigger_concept_ids: [primaryConceptId, ...extraTrigIds],
        match_aliases: matchKeywords,
        catalog_scope: catalogScope.trim() || null,
        force_box2: forceBox2,
        has_plan_tiers: hasPlanTiers,
        is_active: editingBundle?.is_active ?? true,
        sort_order: editingBundle?.sort_order ?? 0,
        tiers: tiers.map((t, idx) => ({
          ...t,
          label: t.label.trim() || (hasPlanTiers ? `Plan ${idx + 1}` : "Default"),
          display_title: t.display_title?.trim() || null,
          display_description: t.display_description?.trim() || null,
          sort_order: idx,
          effects: (t.effects || []).map((e, eIdx) => ({
            ...e,
            sort_order: eIdx,
            display_title: e.display_title?.trim() || null,
            display_value: e.display_value ?? "",
            display_description: e.display_description?.trim() || null,
            icon_hint: e.icon_hint?.trim() || null,
            comparison_value: e.comparison_value?.trim() || null,
          })),
        })),
      });
      onOpenChange(false);
    } catch (err: any) {
      setLocalError(err?.message || "Failed to save bundle.");
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={editingBundle ? `Edit Bundled Benefit — ${editingBundle.name}` : "New Bundled Benefit (Mystery Box)"}
    >
      <div className="max-w-3xl max-h-[82vh] overflow-y-auto p-5 space-y-4 text-xs">
        <p className="text-[var(--rl-text-muted)]">
          Configure a bundled add-on package for <strong>{selectedCompany?.name}</strong>. When active on a quote, it stays in Box 2 and unlocks its plan-specific Box 2 upgrades while removing redundant Box 1 defaults.
        </p>

        {localError && (
          <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700 font-medium">
            {localError}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">Bundle Name *</label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Private Car 365 / Motor Easy Bundle" />
          </div>
          <div>
            <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">Primary Add-On Concept *</label>
            <BenefitCombobox
              concepts={concepts}
              value={primaryConceptId}
              onChange={setPrimaryConceptId}
              placeholder="-- Select Primary Bundle Concept --"
            />
          </div>
          <div>
            <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">Detection Keywords (comma-separated)</label>
            <Input
              value={keywordsText}
              onChange={(e) => setKeywordsText(e.target.value)}
              placeholder="e.g. motor easy bundle, autobuddy, motor shield"
            />
          </div>
          <div>
            <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">Catalog Scope (Optional)</label>
            <Input
              value={catalogScope}
              onChange={(e) => setCatalogScope(e.target.value)}
              placeholder="Blank = all Comprehensive catalogs, or e.g. lite"
            />
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-6 rounded border border-[var(--rl-border)] bg-[var(--rl-bg)] px-3 py-2.5">
          <label className="flex items-center gap-2 font-semibold cursor-pointer">
            <input type="checkbox" checked={forceBox2} onChange={(e) => setForceBox2(e.target.checked)} />
            <span>Always force bundle card into Box 2 (never Box 1)</span>
          </label>
          <label className="flex items-center gap-2 font-semibold cursor-pointer">
            <input
              type="checkbox"
              checked={hasPlanTiers}
              onChange={(e) => {
                const next = e.target.checked;
                setHasPlanTiers(next);
                if (next && tiers.length === 1 && tiers[0].label === "Default") {
                  setTiers([{ ...tiers[0], label: "Plan 1", match_tokens: ["plan 1", "pelan 1", "p1"] }]);
                }
              }}
            />
            <span>Has Plan Tiers (Plan 1 / Plan 2 / Plan 3 / Plan 4)</span>
          </label>
        </div>

        {/* Plan Tiers + Effects */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="font-bold text-[var(--rl-text-strong)] text-sm">
              {hasPlanTiers ? `Plan Tiers (${tiers.length})` : "Default Bundle Effects"}
            </h4>
            {hasPlanTiers && (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                onClick={() =>
                  setTiers((prev) => [
                    ...prev,
                    {
                      label: `Plan ${prev.length + 1}`,
                      match_tokens: [`plan ${prev.length + 1}`, `pelan ${prev.length + 1}`, `p${prev.length + 1}`],
                      is_default_fallback: false,
                      sort_order: prev.length,
                      effects: [emptyEffect(concepts)],
                    },
                  ])
                }
                className="h-7 gap-1 text-xs"
              >
                <Plus size={12} weight="bold" />
                <span>Add Plan Tier</span>
              </Button>
            )}
          </div>

          {tiers.map((tier, tIdx) => (
            <div key={tIdx} className="rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-3 space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2 flex-1">
                  <Input
                    value={tier.label}
                    onChange={(e) =>
                      setTiers((prev) => prev.map((row, i) => (i === tIdx ? { ...row, label: e.target.value } : row)))
                    }
                    placeholder="Tier Label (e.g. Plan 1)"
                    className="h-7 w-36 font-semibold"
                  />
                  <Input
                    value={(tier.match_tokens || []).join(", ")}
                    onChange={(e) =>
                      setTiers((prev) =>
                        prev.map((row, i) =>
                          i === tIdx
                            ? { ...row, match_tokens: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) }
                            : row
                        )
                      )
                    }
                    placeholder="Match tokens (e.g. plan 1, p1)"
                    className="h-7 flex-1 min-w-[180px]"
                  />
                  <label className="flex items-center gap-1 text-[11px] font-medium cursor-pointer">
                    <input
                      type="radio"
                      name="bundle-default-tier"
                      checked={tier.is_default_fallback}
                      onChange={() =>
                        setTiers((prev) => prev.map((row, i) => ({ ...row, is_default_fallback: i === tIdx })))
                      }
                    />
                    <span>Default Fallback</span>
                  </label>
                </div>
                {tiers.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setTiers((prev) => prev.filter((_, i) => i !== tIdx))}
                    className="p-1 text-red-500 hover:text-red-700"
                    title="Remove Tier"
                  >
                    <Trash size={14} />
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 rounded border border-[var(--rl-border)] bg-[var(--rl-bg)] p-2.5">
                <div>
                  <label className="block text-[10px] font-semibold text-[var(--rl-text-muted)] mb-1">
                    Parent Card Title Override (Optional, multi-line supported)
                  </label>
                  <textarea
                    rows={2}
                    value={tier.display_title || ""}
                    onChange={(e) =>
                      setTiers((prev) =>
                        prev.map((row, i) => (i === tIdx ? { ...row, display_title: e.target.value } : row))
                      )
                    }
                    placeholder="Optional per-tier title (e.g. Driver Passenger Protection Plan 1\n意外保险-计划1)"
                    className="w-full rounded border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2 py-1 text-xs focus:outline-none focus:border-[var(--rl-black)]"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-semibold text-[var(--rl-text-muted)] mb-1">
                    Parent Card Description Override (Optional, multi-line supported)
                  </label>
                  <textarea
                    rows={4}
                    value={tier.display_description || ""}
                    onChange={(e) =>
                      setTiers((prev) =>
                        prev.map((row, i) => (i === tIdx ? { ...row, display_description: e.target.value } : row))
                      )
                    }
                    placeholder="Optional per-tier description shown when this plan tier is active"
                    className="w-full rounded border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2 py-1 text-xs focus:outline-none focus:border-[var(--rl-black)]"
                  />
                </div>
              </div>

              <div className="pl-2 border-l-2 border-emerald-200 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-bold text-emerald-900">Unlocked Box 2 Effects ({tier.effects.length})</span>
                  <button
                    type="button"
                    onClick={() =>
                      setTiers((prev) =>
                        prev.map((row, i) =>
                          i === tIdx ? { ...row, effects: [...row.effects, emptyEffect(concepts)] } : row
                        )
                      )
                    }
                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-700 hover:text-emerald-900"
                  >
                    <Plus size={11} weight="bold" />
                    <span>Add Unlocked Benefit</span>
                  </button>
                </div>

                {tier.effects.map((eff, eIdx) => (
                  <div key={eIdx} className="rounded border border-[var(--rl-border)] bg-[var(--rl-bg)] p-2.5 space-y-2">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                      <div>
                        <label className="block text-[10px] font-semibold text-[var(--rl-text-muted)] mb-0.5">Effect Action</label>
                        <select
                          value={eff.effect_type}
                          onChange={(e) =>
                            setTiers((prev) =>
                              prev.map((row, i) =>
                                i === tIdx
                                  ? {
                                      ...row,
                                      effects: row.effects.map((ef, j) =>
                                        j === eIdx ? { ...ef, effect_type: e.target.value as CompanyBenefitBundleEffect["effect_type"] } : ef
                                      ),
                                    }
                                  : row
                              )
                            )
                          }
                          className="h-7 w-full rounded border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2 text-xs"
                        >
                          <option value="upgrade_to_box2">Move Box 1 → Box 2 Upgrade</option>
                          <option value="add_to_box2">Add Extra Benefit to Box 2</option>
                          <option value="hide_from_box1">Hide from Box 1</option>
                        </select>
                      </div>
                      <div className="md:col-span-2 flex items-end gap-2">
                        <div className="flex-1">
                          <label className="block text-[10px] font-semibold text-[var(--rl-text-muted)] mb-0.5">Target Benefit *</label>
                          <BenefitCombobox
                            concepts={concepts}
                            value={eff.target_concept_id}
                            onChange={(val) =>
                              setTiers((prev) =>
                                prev.map((row, i) =>
                                  i === tIdx
                                    ? {
                                        ...row,
                                        effects: row.effects.map((ef, j) => (j === eIdx ? { ...ef, target_concept_id: val } : ef)),
                                      }
                                    : row
                                )
                              )
                            }
                            placeholder="-- Select Target Benefit --"
                          />
                        </div>
                        {tier.effects.length > 1 && (
                          <button
                            type="button"
                            onClick={() =>
                              setTiers((prev) =>
                                prev.map((row, i) =>
                                  i === tIdx ? { ...row, effects: row.effects.filter((_, j) => j !== eIdx) } : row
                                )
                              )
                            }
                            className="p-1.5 text-red-500 hover:text-red-700"
                            title="Remove Effect"
                          >
                            <Trash size={13} />
                          </button>
                        )}
                      </div>
                    </div>

                    {eff.effect_type !== "hide_from_box1" && (
                      <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                        <div className="md:col-span-2">
                          <label className="block text-[10px] font-semibold text-[var(--rl-text-muted)] mb-0.5">Box 2 Card Title</label>
                          <Input
                            value={eff.display_title || ""}
                            onChange={(e) =>
                              setTiers((prev) =>
                                prev.map((row, i) =>
                                  i === tIdx
                                    ? {
                                        ...row,
                                        effects: row.effects.map((ef, j) => (j === eIdx ? { ...ef, display_title: e.target.value } : ef)),
                                      }
                                    : row
                                )
                              )
                            }
                            placeholder="e.g. Towing Assistance (600 km)"
                            className="h-7"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold text-[var(--rl-text-muted)] mb-0.5">Coverage (blank = none)</label>
                          <Input
                            value={eff.display_value || ""}
                            onChange={(e) =>
                              setTiers((prev) =>
                                prev.map((row, i) =>
                                  i === tIdx
                                    ? {
                                        ...row,
                                        effects: row.effects.map((ef, j) => (j === eIdx ? { ...ef, display_value: e.target.value } : ef)),
                                      }
                                    : row
                                )
                              )
                            }
                            placeholder="(Blank)"
                            className="h-7"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold text-[var(--rl-text-muted)] mb-0.5">Comparison Value</label>
                          <Input
                            value={eff.comparison_value || ""}
                            onChange={(e) =>
                              setTiers((prev) =>
                                prev.map((row, i) =>
                                  i === tIdx
                                    ? {
                                        ...row,
                                        effects: row.effects.map((ef, j) => (j === eIdx ? { ...ef, comparison_value: e.target.value } : ef)),
                                      }
                                    : row
                                )
                              )
                            }
                            placeholder="e.g. 600 km / Unlimited"
                            className="h-7"
                          />
                        </div>
                        <div className="md:col-span-3">
                          <label className="block text-[10px] font-semibold text-[var(--rl-text-muted)] mb-0.5">Description</label>
                          <Input
                            value={eff.display_description || ""}
                            onChange={(e) =>
                              setTiers((prev) =>
                                prev.map((row, i) =>
                                  i === tIdx
                                    ? {
                                        ...row,
                                        effects: row.effects.map((ef, j) =>
                                          j === eIdx ? { ...ef, display_description: e.target.value } : ef
                                        ),
                                      }
                                    : row
                                )
                              )
                            }
                            placeholder="24/7 emergency towing assistance..."
                            className="h-7"
                          />
                        </div>
                        <div>
                          <label className="block text-[10px] font-semibold text-[var(--rl-text-muted)] mb-0.5">Icon Style</label>
                          <select
                            value={eff.icon_hint || ""}
                            onChange={(e) =>
                              setTiers((prev) =>
                                prev.map((row, i) =>
                                  i === tIdx
                                    ? {
                                        ...row,
                                        effects: row.effects.map((ef, j) => (j === eIdx ? { ...ef, icon_hint: e.target.value } : ef)),
                                      }
                                    : row
                                )
                              )
                            }
                            className="h-7 w-full rounded border border-[var(--rl-border)] bg-[var(--rl-surface)] px-2 text-xs"
                          >
                            {ICON_HINT_OPTIONS.map((opt) => (
                              <option key={opt.value} value={opt.value}>
                                {opt.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-2 pt-2 border-t border-[var(--rl-border)]">
          <Button type="button" variant="secondary" size="sm" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            size="sm"
            disabled={saving}
            onClick={handleSubmit}
            className="bg-[var(--rl-black)] text-white"
          >
            {saving ? "Saving..." : editingBundle ? "Save Bundle" : "Create Bundle"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
