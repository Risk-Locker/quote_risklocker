"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowClockwise,
  Check,
  CheckCircle,
  Copy,
  FloppyDisk,
  Folder,
  ImageSquare,
  Images,
  Lightning,
  MagnifyingGlass,
  Plus,
  ShieldCheck,
  Star,
  Trash,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { BuilderNav } from "@/components/builder-nav";
import { GuidedTour } from "@/components/guided-tour";
import { TagEditor } from "@/components/tag-editor";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Toggle } from "@/components/ui/toggle";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Asset = {
  id: string;
  label: string;
  asset_kind: string;
  status: string;
  url: string;
  category?: string;
};

type GlobalBenefit = {
  id: string;
  concept_key: string;
  label: string;
  category?: "default" | "addon";
  variants?: string[];
  description: string | null;
  match_dataset: string[];
  sort_order: number;
  default_asset: Asset | null;
  display_overrides?: Record<string, boolean>;
  revision: number;
  status: string;
};

type VisualProfile = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  asset_category: string;
  is_active: boolean;
  status: string;
  total_concepts: number;
  mapped_count: number;
  missing_count: number;
  is_complete: boolean;
  created_at?: string;
  updated_at?: string;
};

type ProfileConceptItem = {
  concept_id: string;
  concept_key: string;
  label: string;
  sort_order: number;
  category: string;
  assigned_asset: {
    id: string;
    label: string;
    category: string;
    url: string;
  } | null;
  is_missing: boolean;
  has_override: boolean;
};

type AutoAssignMatch = {
  concept_id: string;
  concept_key: string;
  concept_label: string;
  sort_order: number;
  matched_asset: {
    id: string;
    label: string;
    original_filename: string;
    url: string;
  } | null;
  confidence: number;
  match_reason: string;
  status: "matched" | "unmatched";
};

type AutoAssignResponse = {
  profile_id: string;
  category: string;
  total_concepts: number;
  total_category_assets: number;
  matched_count: number;
  unmatched_count: number;
  matches: AutoAssignMatch[];
  available_category_assets: Array<{
    id: string;
    label: string;
    original_filename: string;
    url: string;
  }>;
};

function slugify(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

export default function GlobalBenefitsPage() {
  const [benefits, setBenefits] = useState<GlobalBenefit[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [assetCategories, setAssetCategories] = useState<Array<{ category: string; count: number }>>([]);
  const [companies, setCompanies] = useState<Array<{ id: string; name: string }>>([]);
  const [companyIdFilter, setCompanyIdFilter] = useState("all");
  const [companyWorkspace, setCompanyWorkspace] = useState<any>(null);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState<"all" | "default" | "addon">("all");
  const [statusFilter, setStatusFilter] = useState("active");
  const [selectedId, setSelectedId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [justSaved, setJustSaved] = useState(false);
  const [isNew, setIsNew] = useState(false);
  const mountedRef = useRef(true);

  // --- Visual Profile System State ---
  const [visualProfiles, setVisualProfiles] = useState<VisualProfile[]>([]);
  const [selectedProfileId, setSelectedProfileId] = useState<string>("");
  const [selectedProfileDetail, setSelectedProfileDetail] = useState<{
    profile: VisualProfile;
    concepts: ProfileConceptItem[];
  } | null>(null);
  const [showMissingOnly, setShowMissingOnly] = useState(false);

  // Profile Dialogs
  const [newProfileOpen, setNewProfileOpen] = useState(false);
  const [newProfileName, setNewProfileName] = useState("");
  const [newProfileCategory, setNewProfileCategory] = useState("");
  const [newProfileCustomCat, setNewProfileCustomCat] = useState("");
  const [newProfileDesc, setNewProfileDesc] = useState("");
  const [creatingProfile, setCreatingProfile] = useState(false);

  const [cloneProfileOpen, setCloneProfileOpen] = useState(false);
  const [cloneProfileName, setCloneProfileName] = useState("");
  const [cloneProfileCategory, setCloneProfileCategory] = useState("");
  const [cloneProfileDesc, setCloneProfileDesc] = useState("");
  const [cloningProfile, setCloningProfile] = useState(false);

  // Auto-Assign Review Screen Dialog State
  const [autoAssignOpen, setAutoAssignOpen] = useState(false);
  const [autoAssignLoading, setAutoAssignLoading] = useState(false);
  const [autoAssignSaving, setAutoAssignSaving] = useState(false);
  const [autoAssignData, setAutoAssignData] = useState<AutoAssignResponse | null>(null);
  const [assignedOverrides, setAssignedOverrides] = useState<Record<string, string>>({}); // concept_id -> asset_id
  const [autoAssignFilter, setAutoAssignFilter] = useState<"all" | "matched" | "unmatched">("all");
  const [autoAssignSearch, setAutoAssignSearch] = useState("");

  // Form State
  const [formLabel, setFormLabel] = useState("");
  const [formKey, setFormKey] = useState("");
  const [formCategory, setFormCategory] = useState<"default" | "addon">("default");
  const [formVariants, setFormVariants] = useState<string[]>([]);
  const [newVariantInput, setNewVariantInput] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formAssetId, setFormAssetId] = useState("");
  const [formMatch, setFormMatch] = useState<string[]>([]);
  const [formDisplayOverrides, setFormDisplayOverrides] = useState<Record<string, boolean>>({});
  const [formSort, setFormSort] = useState(0);
  const [formActive, setFormActive] = useState(true);

  const activeProfile = useMemo(
    () => visualProfiles.find((p) => p.is_active) || null,
    [visualProfiles]
  );

  const currentProfile = useMemo(
    () => visualProfiles.find((p) => p.id === selectedProfileId) || activeProfile,
    [visualProfiles, selectedProfileId, activeProfile]
  );

  // Filter assets strictly to the active/selected visual profile's asset category (Category Exclusivity Invariant)
  const categoryAssets = useMemo(() => {
    if (!currentProfile?.asset_category) return assets;
    const cat = String(currentProfile.asset_category).toLowerCase();
    return assets.filter((a) => String(a.category || "General").toLowerCase() === cat);
  }, [assets, currentProfile]);

  const filteredAutoAssignMatches = useMemo(() => {
    if (!autoAssignData) return [];
    return autoAssignData.matches.filter((m) => {
      const hasAssign = Boolean(assignedOverrides[m.concept_id]);
      if (autoAssignFilter === "matched" && !hasAssign) return false;
      if (autoAssignFilter === "unmatched" && hasAssign) return false;

      if (autoAssignSearch.trim()) {
        const query = autoAssignSearch.toLowerCase().trim();
        const currentAssetId = assignedOverrides[m.concept_id];
        const activeAsset = autoAssignData.available_category_assets.find((a) => a.id === currentAssetId);
        const matchLabel = (m.concept_label || "").toLowerCase();
        const matchKey = (m.concept_key || "").toLowerCase();
        const matchReason = (m.match_reason || "").toLowerCase();
        const assetLabel = (activeAsset?.label || activeAsset?.original_filename || "").toLowerCase();
        const orderStr = String(m.sort_order || "");

        const matchesQuery =
          matchLabel.includes(query) ||
          matchKey.includes(query) ||
          matchReason.includes(query) ||
          assetLabel.includes(query) ||
          orderStr.includes(query);

        if (!matchesQuery) return false;
      }

      return true;
    });
  }, [autoAssignData, assignedOverrides, autoAssignFilter, autoAssignSearch]);

  const loadProfiles = useCallback(async () => {
    try {
      const res = await api<{ profiles: VisualProfile[] }>("/business/global-benefit-profiles");
      const list = res.profiles || [];
      setVisualProfiles(list);
      return list;
    } catch {
      return [];
    }
  }, []);

  const loadProfileDetail = useCallback(async (profId: string) => {
    if (!profId) return;
    try {
      const res = await api<{ profile: VisualProfile; concepts: ProfileConceptItem[] }>(
        `/business/global-benefit-profiles/${profId}`
      );
      setSelectedProfileDetail(res);
    } catch {
      // Non-fatal
    }
  }, []);

  const loadReferenceData = useCallback(async (profileId?: string) => {
    const profParam = profileId ? `&visual_profile_id=${profileId}` : "";
    const [benefitResult, assetResult, companyResult, catResult] = await Promise.all([
      api<{ benefit_concepts: { items: GlobalBenefit[] } }>(`/business/benefit-concepts?page=1&page_size=100${profParam}`),
      api<{ assets: { items: Asset[] } }>("/business/assets?kind=benefit_art&page=1&page_size=100"),
      api<{ companies: { items: Array<{ id: string; name: string }> } }>("/business/companies?page_size=100"),
      api<{ categories: Array<{ category?: string; name?: string; count: number }> }>("/business/assets/categories"),
    ]);
    return {
      benefits: benefitResult.benefit_concepts.items,
      assets: assetResult.assets.items,
      companies: companyResult.companies?.items || [],
      categories: (catResult.categories || []).map((c) => ({
        category: c.category || c.name || "General",
        count: c.count,
      })),
    };
  }, []);

  const refresh = useCallback(
    async (keepSelection = true, targetProfileId = selectedProfileId) => {
      setError("");
      try {
        const [profiles, refData] = await Promise.all([
          loadProfiles(),
          loadReferenceData(targetProfileId),
        ]);
        if (!mountedRef.current) return;
        setBenefits(refData.benefits);
        setAssets(refData.assets);
        setCompanies(refData.companies);
        setAssetCategories(refData.categories);

        const effProfId = targetProfileId || profiles.find((p) => p.is_active)?.id || profiles[0]?.id || "";
        if (effProfId) {
          await loadProfileDetail(effProfId);
        }

        if (keepSelection && selectedId && !refData.benefits.some((item) => item.id === selectedId)) {
          setSelectedId("");
          setIsNew(false);
        }
      } catch (err) {
        if (mountedRef.current) setError(apiErrorMessage(err));
      }
    },
    [loadProfiles, loadReferenceData, loadProfileDetail, selectedId, selectedProfileId]
  );

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;

    (async () => {
      try {
        const profiles = await loadProfiles();
        if (cancelled) return;
        const active = profiles.find((p) => p.is_active) || profiles[0] || null;
        const profId = active ? active.id : "";
        if (profId) setSelectedProfileId(profId);

        const refData = await loadReferenceData(profId);
        if (cancelled) return;
        setBenefits(refData.benefits);
        setAssets(refData.assets);
        setCompanies(refData.companies);
        setAssetCategories(refData.categories);

        if (profId) {
          await loadProfileDetail(profId);
        }
        if (refData.benefits.length) selectBenefit(refData.benefits[0]);
      } catch (err) {
        if (!cancelled) setError(apiErrorMessage(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      mountedRef.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (companyIdFilter === "all") {
      setCompanyWorkspace(null);
      return;
    }
    let cancelled = false;
    api<{ workspace: any }>(`/business/companies/${companyIdFilter}/workspace`)
      .then((res) => {
        if (!cancelled) setCompanyWorkspace(res.workspace);
      })
      .catch(() => {
        if (!cancelled) setCompanyWorkspace(null);
      });
    return () => {
      cancelled = true;
    };
  }, [companyIdFilter]);

  const insurerConceptKeys = useMemo(() => {
    if (!companyWorkspace) return null;
    const keys = new Set<string>();
    for (const cat of companyWorkspace.catalogs || []) {
      for (const off of cat.offerings || []) {
        if (off.concept_key) keys.add(off.concept_key);
        if (off.concept?.concept_key) keys.add(off.concept.concept_key);
        if (off.concept_id) keys.add(off.concept_id);
        if (off.concept?.id) keys.add(off.concept.id);
      }
    }
    return keys;
  }, [companyWorkspace]);

  // Set of missing concept IDs in the active/selected visual profile
  const missingConceptIds = useMemo(() => {
    if (!selectedProfileDetail?.concepts) return new Set<string>();
    return new Set(
      selectedProfileDetail.concepts.filter((c) => c.is_missing).map((c) => c.concept_id)
    );
  }, [selectedProfileDetail]);

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return benefits.filter((item) => {
      if (insurerConceptKeys && !insurerConceptKeys.has(item.concept_key) && !insurerConceptKeys.has(item.id)) {
        return false;
      }
      if (showMissingOnly && !missingConceptIds.has(item.id)) {
        return false;
      }
      const cat = item.category || (item.sort_order <= 11 ? "default" : "addon");
      if (categoryFilter !== "all" && cat !== categoryFilter) return false;
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      if (!term) return true;
      return (
        item.label.toLowerCase().includes(term) ||
        item.concept_key.toLowerCase().includes(term) ||
        (item.variants || []).some((v) => v.toLowerCase().includes(term))
      );
    });
  }, [benefits, search, categoryFilter, statusFilter, insurerConceptKeys, showMissingOnly, missingConceptIds]);

  const activeCount = useMemo(() => benefits.filter((b) => b.status === "active").length, [benefits]);
  const defaultCount = useMemo(
    () =>
      benefits.filter(
        (b) => b.status === "active" && (b.category || (b.sort_order <= 11 ? "default" : "addon")) === "default"
      ).length,
    [benefits]
  );
  const addonCount = useMemo(
    () =>
      benefits.filter(
        (b) => b.status === "active" && (b.category || (b.sort_order <= 11 ? "default" : "addon")) === "addon"
      ).length,
    [benefits]
  );
  const trashCount = useMemo(() => benefits.filter((b) => b.status === "retired").length, [benefits]);

  const selected = benefits.find((item) => item.id === selectedId) || null;

  function selectBenefit(item: GlobalBenefit) {
    setSelectedId(item.id);
    setIsNew(false);
    setError("");
    setSuccessMessage("");
    setJustSaved(false);
    setFormLabel(item.label);
    setFormKey(item.concept_key);
    setFormCategory(item.category || (item.sort_order <= 11 ? "default" : "addon"));
    setFormVariants([...(item.variants || [])]);
    setNewVariantInput("");
    setFormDescription(item.description || "");

    // Check profile assigned asset or concept default
    const profileAsset = selectedProfileDetail?.concepts.find((c) => c.concept_id === item.id)?.assigned_asset;
    setFormAssetId(profileAsset?.id || item.default_asset?.id || "");

    setFormMatch([...item.match_dataset]);
    setFormDisplayOverrides(item.display_overrides || {});
    setFormSort(item.sort_order || 0);
    setFormActive(item.status === "active");
  }

  function newBenefit() {
    setSelectedId("");
    setIsNew(true);
    setError("");
    setSuccessMessage("");
    setJustSaved(false);
    setFormLabel("");
    setFormKey("");
    setFormCategory(categoryFilter === "addon" ? "addon" : "default");
    setFormVariants([]);
    setNewVariantInput("");
    setFormDescription("");
    setFormAssetId("");
    setFormMatch([]);
    setFormDisplayOverrides({});
    setFormSort(benefits.length + 1);
    setFormActive(true);
  }

  function addVariant() {
    const val = newVariantInput.trim();
    if (!val || formVariants.includes(val)) return;
    setFormVariants([...formVariants, val]);
    setNewVariantInput("");
  }

  function removeVariant(index: number) {
    setFormVariants(formVariants.filter((_, i) => i !== index));
  }

  function toggleFormDisplayOverride(key: string) {
    setFormDisplayOverrides((prev) => {
      const next: Record<string, boolean> = { ...prev };
      if (key === "enabled") {
        const nextEnabled = !prev.enabled;
        next.enabled = nextEnabled;
        if (nextEnabled) {
          next.showCoverage = prev.showCoverage !== false;
          next.showDescription = prev.showDescription !== false;
          next.showCost = prev.showCost !== false;
          next.showAsset = prev.showAsset !== false;
          next.showGroup = prev.showGroup !== false;
        }
        return next;
      }
      next[key] = !(prev[key] !== false);
      return next;
    });
  }

  async function handleProfileSwitch(profId: string) {
    setSelectedProfileId(profId);
    setLoading(true);
    try {
      await loadProfileDetail(profId);
      const refData = await loadReferenceData(profId);
      setBenefits(refData.benefits);
      if (selectedId) {
        const updated = refData.benefits.find((b) => b.id === selectedId);
        if (updated) selectBenefit(updated);
      }
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function handleActivateProfile() {
    if (!currentProfile) return;
    setError("");
    try {
      await api(`/business/global-benefit-profiles/${currentProfile.id}/activate`, { method: "POST" });
      setSuccessMessage(`Visual Profile "${currentProfile.name}" is now ACTIVE across all quotations!`);
      setTimeout(() => setSuccessMessage(""), 4000);
      await refresh(true, currentProfile.id);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function handleDeleteProfile() {
    if (!currentProfile || currentProfile.is_active) return;
    if (!confirm(`Are you sure you want to delete visual profile "${currentProfile.name}"?`)) return;
    setError("");
    try {
      await api(`/business/global-benefit-profiles/${currentProfile.id}`, { method: "DELETE" });
      setSuccessMessage(`Profile "${currentProfile.name}" deleted.`);
      setTimeout(() => setSuccessMessage(""), 4000);
      const nextActive = visualProfiles.find((p) => p.is_active && p.id !== currentProfile.id);
      setSelectedProfileId(nextActive?.id || "");
      await refresh(false, nextActive?.id);
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function handleCreateProfileSubmit() {
    if (!newProfileName.trim()) {
      setError("Enter a profile name.");
      return;
    }
    const cat = newProfileCategory === "__new__" ? newProfileCustomCat.trim() : newProfileCategory.trim();
    if (!cat) {
      setError("Please select or specify an asset folder/category.");
      return;
    }
    setCreatingProfile(true);
    setError("");
    try {
      const res = await api<{ profile: VisualProfile }>(`/business/global-benefit-profiles`, {
        method: "POST",
        body: JSON.stringify({
          name: newProfileName.trim(),
          asset_category: cat,
          description: newProfileDesc.trim() || null,
        }),
      });
      setNewProfileOpen(false);
      setNewProfileName("");
      setNewProfileCustomCat("");
      setNewProfileDesc("");
      setSuccessMessage(`Created profile "${res.profile.name}".`);
      setTimeout(() => setSuccessMessage(""), 4000);
      setSelectedProfileId(res.profile.id);
      await refresh(true, res.profile.id);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setCreatingProfile(false);
    }
  }

  async function handleCloneProfileSubmit() {
    if (!currentProfile) return;
    setCloningProfile(true);
    setError("");
    try {
      const cat = cloneProfileCategory || currentProfile.asset_category;
      const res = await api<{ profile: VisualProfile }>(
        `/business/global-benefit-profiles/${currentProfile.id}/clone`,
        {
          method: "POST",
          body: JSON.stringify({
            name: cloneProfileName.trim() || `Clone of ${currentProfile.name}`,
            asset_category: cat,
            description: cloneProfileDesc.trim() || currentProfile.description,
          }),
        }
      );
      setCloneProfileOpen(false);
      setCloneProfileName("");
      setCloneProfileDesc("");
      setSuccessMessage(`Cloned profile into "${res.profile.name}"!`);
      setTimeout(() => setSuccessMessage(""), 4000);
      setSelectedProfileId(res.profile.id);
      await refresh(true, res.profile.id);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setCloningProfile(false);
    }
  }

  async function handleOpenAutoAssign() {
    if (!currentProfile) return;
    setAutoAssignLoading(true);
    setError("");
    try {
      const data = await api<AutoAssignResponse>(
        `/business/global-benefit-profiles/${currentProfile.id}/auto-assign`,
        { method: "POST" }
      );
      setAutoAssignData(data);
      const initialMap: Record<string, string> = {};
      for (const m of data.matches) {
        if (m.matched_asset) {
          initialMap[m.concept_id] = m.matched_asset.id;
        }
      }
      setAssignedOverrides(initialMap);
      setAutoAssignSearch("");
      setAutoAssignFilter("all");
      setAutoAssignOpen(true);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setAutoAssignLoading(false);
    }
  }

  async function handleSaveAutoAssignments() {
    if (!currentProfile || !autoAssignData) return;
    setAutoAssignSaving(true);
    setError("");
    try {
      const items = Object.entries(assignedOverrides)
        .filter(([, assetId]) => Boolean(assetId))
        .map(([conceptId, assetId]) => ({
          concept_id: conceptId,
          asset_id: assetId,
        }));

      await api(`/business/global-benefit-profiles/${currentProfile.id}/assets`, {
        method: "PUT",
        body: JSON.stringify({ items }),
      });

      setAutoAssignOpen(false);
      setSuccessMessage(`Saved ${items.length} icon assignments for profile "${currentProfile.name}"!`);
      setTimeout(() => setSuccessMessage(""), 4000);
      await refresh(true, currentProfile.id);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setAutoAssignSaving(false);
    }
  }

  async function saveBenefit() {
    if (!formLabel.trim()) {
      setError("Enter a benefit name.");
      return;
    }
    const key = formKey.trim() || slugify(formLabel);
    if (!key) {
      setError("Enter a stable key for this benefit.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccessMessage("");
    try {
      const payload: Record<string, unknown> = {
        concept_key: key,
        label: formLabel.trim(),
        category: formCategory,
        variants: formVariants,
        description: formDescription.trim() || null,
        default_asset_id: formAssetId || null,
        display_template: "{label}",
        required_variables: [],
        match_dataset: formMatch,
        demo_value: null,
        display_overrides: formDisplayOverrides,
        sort_order: Math.max(0, Number(formSort) || 0),
        status: formActive ? "active" : "inactive",
      };
      if (!isNew && selected) {
        payload.id = selected.id;
        payload.base_revision = selected.revision;
      }
      const saved = await api<{ benefit_concept: GlobalBenefit }>("/business/benefit-concepts", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      // If a visual profile is active, also bind this asset to the visual profile
      if (currentProfile && formAssetId && saved.benefit_concept) {
        const existingAssignments = (selectedProfileDetail?.concepts || [])
          .filter((c) => c.assigned_asset && c.concept_id !== saved.benefit_concept.id)
          .map((c) => ({
            concept_id: c.concept_id,
            asset_id: c.assigned_asset!.id,
          }));
        existingAssignments.push({
          concept_id: saved.benefit_concept.id,
          asset_id: formAssetId,
        });
        await api(`/business/global-benefit-profiles/${currentProfile.id}/assets`, {
          method: "PUT",
          body: JSON.stringify({ items: existingAssignments }),
        });
      }

      await refresh(false, currentProfile?.id);
      selectBenefit(saved.benefit_concept);
      setJustSaved(true);
      setSuccessMessage(`Benefit "${saved.benefit_concept.label}" successfully saved!`);
      setTimeout(() => setJustSaved(false), 3500);
      setTimeout(() => setSuccessMessage(""), 5000);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const [deleting, setDeleting] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  async function handleDeleteConcept() {
    if (!selected) return;
    setDeleting(true);
    setError("");
    try {
      await api(`/business/benefit-concepts/${selected.id}`, { method: "DELETE" });
      setShowDeleteConfirm(false);
      const deletedLabel = selected.label;
      await refresh(false, currentProfile?.id);
      setSelectedId("");
      setIsNew(false);
      setSuccessMessage(`Benefit "${deletedLabel}" was moved to Trash.`);
      setTimeout(() => setSuccessMessage(""), 5000);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  }

  async function handleRestoreConcept() {
    if (!selected) return;
    setRestoring(true);
    setError("");
    try {
      await api(`/business/benefit-concepts/${selected.id}/restore`, { method: "POST" });
      const restoredLabel = selected.label;
      await refresh(false, currentProfile?.id);
      setSuccessMessage(`Benefit "${restoredLabel}" restored to active library!`);
      setTimeout(() => setSuccessMessage(""), 5000);
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setRestoring(false);
    }
  }

  if (loading && !benefits.length) {
    return (
      <AppShell>
        <PageLoading />
      </AppShell>
    );
  }

  return (
    <AppShell>
      <section className="grid gap-5 max-w-6xl mx-auto pb-16">
        <header>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="mb-1 text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--rl-red)]">
                Builder & Catalog
              </p>
              <h1 className="m-0 font-[var(--font-manrope)] text-[30px] font-bold text-[var(--rl-text-strong)]">
                Global Benefits & Visual Profiles
              </h1>
              <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
                Manage global benefit definitions, visual image profiles, and folder-exclusive artwork styles for quotation rendering.
              </p>
            </div>
            <GuidedTour
              storageKey="tour:global-benefits"
              title="Benefit Library & Profiles"
              description="Manage the 63 canonical global benefits and their bound artwork. Switch or clone visual profiles to instantly theme all quotation cards."
              steps={[
                {
                  target: ".rl-tour-profile",
                  title: "Visual Profiles",
                  body: "Select or clone visual profiles (e.g. 3D Isometric, Minimal Line Art). Each profile is bound to a single asset folder for guaranteed visual style consistency.",
                },
                {
                  target: ".rl-tour-list",
                  title: "Benefit list",
                  body: "All global benefits. Benefits with missing images in the selected profile folder will show a warning marker.",
                },
                {
                  target: ".rl-tour-form",
                  title: "Benefit definition",
                  body: "Artwork icons in the editor are filtered strictly to your profile's folder category.",
                },
              ]}
            />
          </div>
        </header>

        <BuilderNav />

        {error ? (
          <div
            role="alert"
            className="flex items-center justify-between gap-3 border-l-4 border-[var(--rl-red)] bg-[var(--rl-red-light)] px-4 py-3 text-[13px] font-medium text-[var(--rl-red)]"
          >
            <div className="flex items-center gap-2">
              <WarningCircle size={18} weight="bold" />
              <span>{error}</span>
            </div>
            <Button variant="ghost" size="sm" icon={<ArrowClockwise size={14} />} onClick={() => refresh()}>
              Retry
            </Button>
          </div>
        ) : null}

        {successMessage ? (
          <div className="flex items-center gap-2 rounded bg-[var(--rl-success)]/15 border border-[var(--rl-success)] px-4 py-2.5 text-[13px] font-semibold text-[var(--rl-success)]">
            <CheckCircle size={18} weight="fill" />
            <span>{successMessage}</span>
          </div>
        ) : null}

        {/* --- VISUAL PROFILE CONTROLLER BAR --- */}
        <div className="rl-tour-profile rounded-[var(--rl-radius-sm)] border-2 border-[var(--rl-border-strong)] bg-white p-3.5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                Visual Profile:
              </span>

              <Select
                value={selectedProfileId}
                onChange={(e) => handleProfileSwitch(e.target.value)}
                className="w-64 text-xs font-bold"
              >
                {visualProfiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.is_active ? "⭐ [Active] " : "[Draft] "}
                    {p.name} ({p.mapped_count}/{p.total_concepts})
                  </option>
                ))}
              </Select>

              {currentProfile ? (
                <>
                  <span
                    className={`rounded px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
                      currentProfile.is_active
                        ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                        : "bg-amber-100 text-amber-800 border border-amber-300"
                    }`}
                  >
                    {currentProfile.is_active ? "Active Profile" : "Draft Profile"}
                  </span>

                  <span className="flex items-center gap-1 rounded bg-[var(--rl-bg)] border border-[var(--rl-border)] px-2.5 py-0.5 text-[11px] font-medium text-[var(--rl-text-strong)]">
                    <Folder size={13} weight="fill" className="text-[var(--rl-text-muted)]" />
                    <span>Folder: <strong>{currentProfile.asset_category}</strong></span>
                  </span>

                  {currentProfile.missing_count > 0 ? (
                    <button
                      type="button"
                      onClick={() => setShowMissingOnly(!showMissingOnly)}
                      className={`flex items-center gap-1.5 rounded px-2.5 py-0.5 text-[11px] font-bold transition-all ${
                        showMissingOnly
                          ? "bg-amber-500 text-white shadow-xs"
                          : "bg-amber-50 text-amber-900 border border-amber-300 hover:bg-amber-100"
                      }`}
                      title="Click to filter benefits with missing images"
                    >
                      <WarningCircle size={13} weight="fill" />
                      <span>{currentProfile.missing_count} Missing Image{currentProfile.missing_count > 1 ? "s" : ""}</span>
                      <span className="text-[10px] underline ml-0.5">{showMissingOnly ? "(Show All)" : "(Filter)"}</span>
                    </button>
                  ) : (
                    <span className="flex items-center gap-1 rounded bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700">
                      <CheckCircle size={13} weight="fill" />
                      <span>{currentProfile.mapped_count}/{currentProfile.total_concepts} Mapped</span>
                    </span>
                  )}
                </>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={handleOpenAutoAssign}
                disabled={autoAssignLoading || !currentProfile}
                title="Automatically match image names in folder to global benefits"
              >
                <Lightning size={14} weight="fill" className="text-amber-600" />
                Auto-assign from folder
              </Button>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  if (currentProfile) {
                    setCloneProfileName(`Clone of ${currentProfile.name}`);
                    setCloneProfileCategory(currentProfile.asset_category);
                    setCloneProfileDesc(currentProfile.description || "");
                    setCloneProfileOpen(true);
                  }
                }}
              >
                <Copy size={14} weight="bold" />
                Clone profile
              </Button>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setNewProfileName("");
                  setNewProfileCategory(assetCategories[0]?.category || "General");
                  setNewProfileCustomCat("");
                  setNewProfileDesc("");
                  setNewProfileOpen(true);
                }}
              >
                <Plus size={14} weight="bold" />
                New profile
              </Button>

              {currentProfile && !currentProfile.is_active ? (
                <Button size="sm" onClick={handleActivateProfile}>
                  <Star size={14} weight="fill" />
                  Set as active
                </Button>
              ) : null}

              {currentProfile && !currentProfile.is_active ? (
                <button
                  type="button"
                  onClick={handleDeleteProfile}
                  className="rounded p-1.5 text-[var(--rl-danger)] hover:bg-red-50"
                  title="Delete this draft profile"
                >
                  <Trash size={15} />
                </button>
              ) : null}
            </div>
          </div>
        </div>

        {/* Category Tabs & Insurer Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-2.5 shadow-xs">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setCategoryFilter("all");
                setStatusFilter("active");
                setShowMissingOnly(false);
              }}
              className={`rounded-md px-3 py-1.5 text-xs font-bold transition-all ${
                categoryFilter === "all" && statusFilter === "active" && !showMissingOnly
                  ? "bg-[var(--rl-black)] text-white shadow-xs"
                  : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              All Active ({activeCount})
            </button>
            <button
              type="button"
              onClick={() => {
                setCategoryFilter("default");
                setStatusFilter("active");
                setShowMissingOnly(false);
              }}
              className={`rounded-md px-3 py-1.5 text-xs font-bold transition-all ${
                categoryFilter === "default" && statusFilter === "active" && !showMissingOnly
                  ? "bg-[var(--rl-black)] text-white shadow-xs"
                  : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              Default / Global Benefits ({defaultCount})
            </button>
            <button
              type="button"
              onClick={() => {
                setCategoryFilter("addon");
                setStatusFilter("active");
                setShowMissingOnly(false);
              }}
              className={`rounded-md px-3 py-1.5 text-xs font-bold transition-all ${
                categoryFilter === "addon" && statusFilter === "active" && !showMissingOnly
                  ? "bg-[var(--rl-black)] text-white shadow-xs"
                  : "bg-white border border-[var(--rl-border)] text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              }`}
            >
              Unique Add-ons ({addonCount})
            </button>
            <button
              type="button"
              onClick={() => {
                setCategoryFilter("all");
                setStatusFilter("retired");
                setShowMissingOnly(false);
              }}
              className={`rounded-md px-3 py-1.5 text-xs font-bold transition-all ${
                statusFilter === "retired"
                  ? "bg-red-600 text-white shadow-xs"
                  : "bg-white border border-red-200 text-red-700 hover:bg-red-50"
              }`}
            >
              🗑️ Trash ({trashCount})
            </button>

            {companies.length > 0 ? (
              <select
                aria-label="Filter by insurance company"
                value={companyIdFilter}
                onChange={(e) => setCompanyIdFilter(e.target.value)}
                className="h-8 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white px-2 text-xs font-semibold text-[var(--rl-text-strong)] shadow-xs focus:outline-none focus:ring-1 focus:ring-[var(--rl-black)]"
              >
                <option value="all">🏢 All Insurers</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    🏢 {c.name}
                  </option>
                ))}
              </select>
            ) : null}
          </div>

          <Button size="sm" icon={<Plus size={14} weight="bold" />} onClick={newBenefit}>
            + Add New Concept
          </Button>
        </div>

        <div className="min-h-[680px] overflow-hidden border border-[var(--rl-border)] bg-[var(--rl-surface)] shadow-card xl:grid xl:grid-cols-[330px_minmax(400px,1fr)]">
          {/* SIDEBAR LIST */}
          <aside className="rl-tour-list border-b border-[var(--rl-border)] bg-[#fafafa] xl:border-b-0 xl:border-r" aria-label="Global benefits list">
            <div className="border-b border-[var(--rl-border)] p-3">
              <div className="grid gap-2">
                <label className="relative block">
                  <MagnifyingGlass size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]" />
                  <Input
                    aria-label="Search benefits"
                    className="h-8 pl-8 text-xs"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    placeholder="Search name, key, or plan..."
                  />
                </label>
                <Select
                  aria-label="Filter by status"
                  className="h-8 text-xs"
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                >
                  <option value="active">Active only</option>
                  <option value="retired">Trash / Deleted ({trashCount})</option>
                  <option value="all">All (Including Trash)</option>
                  <option value="inactive">Inactive only</option>
                </Select>
              </div>
            </div>

            <div className="max-h-[580px] overflow-y-auto p-2">
              {filtered.length ? (
                filtered.map((item) => {
                  const active = item.id === selectedId;
                  const hasVariants = (item.variants || []).length > 0;
                  const isMissing = missingConceptIds.has(item.id);

                  // Resolved asset icon from profile or default
                  const profAsset = selectedProfileDetail?.concepts.find((c) => c.concept_id === item.id)?.assigned_asset;
                  const iconUrl = profAsset?.url ? fileUrl(profAsset.url) : item.default_asset ? fileUrl(item.default_asset.url) : "";

                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => selectBenefit(item)}
                      className={`mb-1.5 grid w-full grid-cols-[36px_1fr] items-center gap-2.5 rounded border-l-2 p-2 text-left transition ${
                        active
                          ? "border-[var(--rl-red)] bg-white shadow-xs ring-1 ring-[var(--rl-border)]"
                          : "border-transparent hover:bg-white"
                      }`}
                    >
                      <span className="grid h-9 w-9 place-items-center rounded border border-[var(--rl-border)] bg-[var(--rl-bg)]">
                        {iconUrl ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img src={iconUrl} alt="" loading="lazy" className="max-h-7 max-w-7 object-contain" />
                        ) : (
                          <ShieldCheck size={16} className="text-[var(--rl-text-muted)]" />
                        )}
                      </span>
                      <div className="min-w-0">
                        <span className="block truncate text-xs font-bold text-[var(--rl-text-strong)]">
                          {item.label}
                        </span>
                        <div className="flex items-center gap-1.5 mt-0.5">
                          <span className="truncate font-mono text-[10px] text-[var(--rl-text-muted)]">
                            #{item.sort_order} · {item.concept_key}
                          </span>
                          {isMissing ? (
                            <span className="shrink-0 rounded bg-amber-100 px-1 text-[9px] font-bold text-amber-800 border border-amber-300">
                              ⚠️ Missing Image
                            </span>
                          ) : null}
                          {item.status === "retired" ? (
                            <span className="shrink-0 rounded bg-red-50 px-1 text-[9px] font-bold text-red-700 border border-red-200">
                              Trash
                            </span>
                          ) : null}
                          {hasVariants ? (
                            <span className="shrink-0 rounded bg-[var(--rl-bg)] px-1 text-[9px] font-semibold text-[var(--rl-text-strong)] border border-[var(--rl-border)]">
                              {item.variants?.length} Plans
                            </span>
                          ) : null}
                        </div>
                        {item.description && (
                          <p className="mt-0.5 truncate text-[10px] text-[var(--rl-text-muted)] italic leading-snug">
                            {item.description}
                          </p>
                        )}
                      </div>
                    </button>
                  );
                })
              ) : (
                <p className="p-4 text-xs text-[var(--rl-text-muted)] text-center">
                  {showMissingOnly
                    ? "Great news! No benefits have missing images in this profile."
                    : "No benefits match your filter."}
                </p>
              )}
            </div>
          </aside>

          {/* MAIN EDIT PANEL */}
          <main className="rl-tour-form flex flex-col justify-between overflow-y-auto p-6 bg-white" aria-label="Global benefit details">
            {selected || isNew ? (
              <div className="grid gap-6 max-w-2xl">
                {/* Header info */}
                <div className="flex items-center justify-between border-b border-[var(--rl-border)] pb-4">
                  <div>
                    <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">
                      {isNew ? "New Global Benefit Concept" : selected?.label}
                    </h2>
                    <p className="text-xs text-[var(--rl-text-muted)]">
                      {isNew
                        ? "Define a new universal insurance benefit."
                        : `Concept key: ${selected?.concept_key} · Revision: ${selected?.revision}`}
                    </p>
                  </div>
                  {!isNew && selected?.status === "retired" ? (
                    <Button size="sm" variant="secondary" onClick={handleRestoreConcept} disabled={restoring}>
                      Restore from Trash
                    </Button>
                  ) : !isNew && selected ? (
                    <button
                      type="button"
                      onClick={() => setShowDeleteConfirm(true)}
                      className="text-xs font-semibold text-[var(--rl-danger)] hover:underline flex items-center gap-1"
                    >
                      <Trash size={14} /> Move to Trash
                    </button>
                  ) : null}
                </div>

                {/* Core Properties */}
                <div className="grid gap-4 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-4 bg-[#fbfbfb]">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-xs font-bold uppercase tracking-[0.12em] text-[var(--rl-text-strong)]">
                        Core Benefit Properties
                      </h3>
                      <p className="text-[12px] text-[var(--rl-text-muted)]">
                        Visual artwork is strictly bound to profile folder <strong>"{currentProfile?.asset_category}"</strong>.
                      </p>
                    </div>
                    <span className="rounded-full bg-[var(--rl-bg)] border border-[var(--rl-border)] px-3 py-1 text-[11px] font-bold text-[var(--rl-text-strong)]">
                      {formCategory === "default" ? "🛡️ Default Benefit" : "✨ Add-on Benefit"}
                    </span>
                  </div>

                  {/* 1. Image / Artwork (Bound to Profile Category) */}
                  <div className="grid gap-1.5">
                    <label className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center justify-between">
                      <span>
                        1. Benefit Image / Icon <span className="text-[var(--rl-red)]">*</span>
                      </span>
                      <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">
                        Category folder: 📁 {currentProfile?.asset_category || "General"}
                      </span>
                    </label>
                    <div className="flex items-center gap-3 p-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)]">
                      <span className="grid h-12 w-12 shrink-0 place-items-center rounded-lg border border-[var(--rl-border)] bg-white shadow-xs">
                        {formAssetId ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={fileUrl(assets.find((a) => a.id === formAssetId)?.url || "")}
                            alt=""
                            className="max-h-9 max-w-9 object-contain"
                          />
                        ) : (
                          <ImageSquare size={24} className="text-[var(--rl-text-muted)]" />
                        )}
                      </span>
                      <div className="flex-1 min-w-0">
                        <Select
                          value={formAssetId}
                          onChange={(e) => setFormAssetId(e.target.value)}
                          className="text-xs font-medium bg-white"
                        >
                          <option value="">(Select Artwork Icon from "{currentProfile?.asset_category}")...</option>
                          {categoryAssets.map((asset) => (
                            <option key={asset.id} value={asset.id}>
                              🖼️ {asset.label}
                            </option>
                          ))}
                        </Select>
                        <p className="mt-1 text-[11px] text-[var(--rl-text-muted)] truncate">
                          {formAssetId
                            ? `Selected: ${assets.find((a) => a.id === formAssetId)?.label}`
                            : `Showing ${categoryAssets.length} icons in "${currentProfile?.asset_category}".`}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* 2. Benefit Title */}
                  <div className="grid gap-1.5">
                    <label className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center justify-between">
                      <span>
                        2. Benefit Title <span className="text-[var(--rl-red)]">*</span>
                      </span>
                      <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">Official display title</span>
                    </label>
                    <Input
                      value={formLabel}
                      onChange={(e) => {
                        setFormLabel(e.target.value);
                        if (isNew) setFormKey(slugify(e.target.value));
                      }}
                      placeholder="e.g. Towing Assistance, Windscreen, Legal Liability..."
                      className="text-xs font-semibold h-9"
                    />
                  </div>

                  {/* 3. Short Description */}
                  <div className="grid gap-1.5">
                    <label className="text-xs font-bold text-[var(--rl-text-strong)] flex items-center justify-between">
                      <span>
                        3. Benefit Short Description <span className="text-[var(--rl-red)]">*</span>
                      </span>
                      <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">
                        Clear summary of coverage / limit
                      </span>
                    </label>
                    <Textarea
                      value={formDescription}
                      onChange={(e) => setFormDescription(e.target.value)}
                      rows={3}
                      placeholder="e.g. 24/7 emergency towing assistance to nearest workshop or preferred location..."
                      className="text-xs"
                    />
                  </div>
                </div>

                {/* Template Display Defaults */}
                <div className="grid gap-3 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex flex-col">
                      <span className="text-xs font-bold text-[var(--rl-text-strong)]">Hard Display Override</span>
                      <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">
                        Force visibility regardless of draft settings
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => toggleFormDisplayOverride("enabled")}
                      className={`text-[10px] font-bold px-2 py-0.5 rounded transition-all ${
                        formDisplayOverrides.enabled
                          ? "bg-emerald-100 text-emerald-800"
                          : "bg-[var(--rl-border)] text-[var(--rl-text-muted)]"
                      }`}
                    >
                      {formDisplayOverrides.enabled ? "ENABLED" : "DISABLED"}
                    </button>
                  </div>
                  {formDisplayOverrides.enabled && (
                    <div className="grid grid-cols-5 gap-2 text-xs pt-2 border-t border-[var(--rl-border)] mt-1">
                      <button
                        type="button"
                        onClick={() => toggleFormDisplayOverride("showCoverage")}
                        className={`rounded border py-2 text-center font-bold transition-all ${
                          formDisplayOverrides.showCoverage !== false
                            ? "bg-red-50 border-red-300 text-red-700"
                            : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-[var(--rl-text-muted)]"
                        }`}
                      >
                        Coverage
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleFormDisplayOverride("showDescription")}
                        className={`rounded border py-2 text-center font-bold transition-all ${
                          formDisplayOverrides.showDescription !== false
                            ? "bg-red-50 border-red-300 text-red-700"
                            : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-[var(--rl-text-muted)]"
                        }`}
                      >
                        Description
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleFormDisplayOverride("showCost")}
                        className={`rounded border py-2 text-center font-bold transition-all ${
                          formDisplayOverrides.showCost !== false
                            ? "bg-red-50 border-red-300 text-red-700"
                            : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-[var(--rl-text-muted)]"
                        }`}
                      >
                        Cost
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleFormDisplayOverride("showAsset")}
                        className={`rounded border py-2 text-center font-bold transition-all ${
                          formDisplayOverrides.showAsset !== false
                            ? "bg-red-50 border-red-300 text-red-700"
                            : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-[var(--rl-text-muted)]"
                        }`}
                      >
                        Image
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleFormDisplayOverride("showGroup")}
                        className={`rounded border py-2 text-center font-bold transition-all ${
                          formDisplayOverrides.showGroup !== false
                            ? "bg-red-50 border-red-300 text-red-700"
                            : "bg-[var(--rl-bg)] border-[var(--rl-border)] text-[var(--rl-text-muted)]"
                        }`}
                      >
                        Group
                      </button>
                    </div>
                  )}
                </div>

                {/* Plan Variants */}
                <div className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h4 className="text-xs font-bold text-[var(--rl-text-strong)]">Plan Variations</h4>
                      <p className="text-[11px] text-[var(--rl-text-muted)]">
                        Internal variants for multi-plan add-ons (e.g. 50km, 100km, Unlimited).
                      </p>
                    </div>
                    <span className="text-xs font-bold text-[var(--rl-text-muted)]">
                      {formVariants.length} variants
                    </span>
                  </div>
                  <div className="flex gap-2 mt-2">
                    <Input
                      value={newVariantInput}
                      onChange={(e) => setNewVariantInput(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addVariant();
                        }
                      }}
                      placeholder="Add plan variation..."
                      className="text-xs h-8"
                    />
                    <Button size="sm" variant="secondary" onClick={addVariant}>
                      Add
                    </Button>
                  </div>
                  {formVariants.length ? (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {formVariants.map((v, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1 rounded bg-[var(--rl-bg)] border border-[var(--rl-border)] px-2 py-0.5 text-xs font-medium"
                        >
                          {v}
                          <button
                            type="button"
                            onClick={() => removeVariant(idx)}
                            className="text-[var(--rl-text-muted)] hover:text-red-600"
                          >
                            <X size={12} />
                          </button>
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>

                {/* Save button */}
                <div className="flex items-center justify-between pt-4 border-t border-[var(--rl-border)]">
                  <div className="flex items-center gap-2">
                    <Toggle checked={formActive} onChange={setFormActive} label="Concept Active" />
                  </div>
                  <Button onClick={saveBenefit} disabled={saving} className="min-w-32">
                    {saving ? (
                      "Saving..."
                    ) : justSaved ? (
                      <>
                        <Check size={16} weight="bold" /> Saved
                      </>
                    ) : (
                      <>
                        <FloppyDisk size={16} weight="bold" /> Save Concept
                      </>
                    )}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="grid h-full place-items-center text-center p-8">
                <div>
                  <ShieldCheck size={36} className="mx-auto text-[var(--rl-text-muted)]" />
                  <p className="mt-3 font-semibold text-[var(--rl-text-strong)]">Select a Benefit</p>
                  <p className="mt-1 text-xs text-[var(--rl-text-muted)]">
                    Pick any benefit from the left list to review its visual profile icon and properties.
                  </p>
                </div>
              </div>
            )}
          </main>
        </div>
      </section>

      {/* --- MODAL 1: ASSIGNED SITUATION REVIEW SCREEN --- */}
      <Dialog
        open={autoAssignOpen}
        onOpenChange={setAutoAssignOpen}
        title="Assigned Situation Review Screen"
        description={`Review and adjust smart icon assignments between folder "${autoAssignData?.category || ""}" and the ${autoAssignData?.total_concepts || 63} global benefit concepts.`}
        onConfirm={handleSaveAutoAssignments}
        confirmLabel={autoAssignSaving ? "Saving assignments..." : `Confirm & Save ${Object.keys(assignedOverrides).length} Assignments`}
        loading={autoAssignSaving}
        maxWidth="4xl"
      >
        <div className="grid gap-4">
          {autoAssignData ? (
            <>
              {/* Summary Stats */}
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-[var(--rl-bg)] border border-[var(--rl-border)] p-3.5">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg bg-[var(--rl-surface)] border border-[var(--rl-border)] flex items-center justify-center text-lg shrink-0 shadow-xs">
                    📁
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-[var(--rl-text-strong)]">
                        {autoAssignData.category}
                      </span>
                      <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--rl-surface)] border border-[var(--rl-border)] text-[var(--rl-text-muted)] font-medium">
                        Target Folder
                      </span>
                    </div>
                    <p className="text-[11px] text-[var(--rl-text-muted)] mt-0.5">
                      Found {autoAssignData.total_category_assets} images in folder · {autoAssignData.total_concepts} total benefit concepts
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 rounded-md bg-emerald-50 text-emerald-800 border border-emerald-200 px-2.5 py-1 text-xs font-bold shadow-xs">
                      <CheckCircle size={14} weight="fill" className="text-emerald-600" />
                      {Object.keys(assignedOverrides).length} Matched
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-50 text-amber-800 border border-amber-200 px-2.5 py-1 text-xs font-bold shadow-xs">
                      <WarningCircle size={14} weight="fill" className="text-amber-600" />
                      {Math.max(0, autoAssignData.total_concepts - Object.keys(assignedOverrides).length)} Unassigned
                    </span>
                  </div>

                  <div className="hidden sm:flex flex-col items-end gap-1 pl-2 border-l border-[var(--rl-border)]">
                    <span className="text-[10px] text-[var(--rl-text-muted)] font-medium">
                      {Math.round((Object.keys(assignedOverrides).length / (autoAssignData.total_concepts || 1)) * 100)}% Complete
                    </span>
                    <div className="w-20 h-1.5 rounded-full bg-[var(--rl-border)] overflow-hidden">
                      <div
                        className="h-full bg-emerald-600 rounded-full transition-all duration-300"
                        style={{
                          width: `${Math.min(100, Math.round((Object.keys(assignedOverrides).length / (autoAssignData.total_concepts || 1)) * 100))}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Filter & Search Bar */}
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rl-border)] pb-2.5">
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => setAutoAssignFilter("all")}
                    className={`text-xs px-3 py-1.5 rounded-md font-semibold transition-colors ${
                      autoAssignFilter === "all"
                        ? "bg-[var(--rl-black)] text-white shadow-xs"
                        : "text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)] hover:text-[var(--rl-text-strong)]"
                    }`}
                  >
                    All ({autoAssignData.matches.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setAutoAssignFilter("matched")}
                    className={`text-xs px-3 py-1.5 rounded-md font-semibold transition-colors ${
                      autoAssignFilter === "matched"
                        ? "bg-[var(--rl-black)] text-white shadow-xs"
                        : "text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)] hover:text-[var(--rl-text-strong)]"
                    }`}
                  >
                    Matched ({Object.keys(assignedOverrides).length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setAutoAssignFilter("unmatched")}
                    className={`text-xs px-3 py-1.5 rounded-md font-semibold transition-colors ${
                      autoAssignFilter === "unmatched"
                        ? "bg-[var(--rl-black)] text-white shadow-xs"
                        : "text-[var(--rl-text-muted)] hover:bg-[var(--rl-bg)] hover:text-[var(--rl-text-strong)]"
                    }`}
                  >
                    Unassigned ({Math.max(0, autoAssignData.total_concepts - Object.keys(assignedOverrides).length)})
                  </button>
                </div>

                <div className="relative flex-1 min-w-[200px] max-w-xs">
                  <MagnifyingGlass
                    size={14}
                    className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)] pointer-events-none"
                  />
                  <Input
                    value={autoAssignSearch}
                    onChange={(e) => setAutoAssignSearch(e.target.value)}
                    placeholder="Search benefit name, key, or asset..."
                    className="h-8 pl-8 pr-7 text-xs"
                  />
                  {autoAssignSearch && (
                    <button
                      type="button"
                      onClick={() => setAutoAssignSearch("")}
                      className="absolute right-2 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              </div>

              {/* Matches List */}
              <div className="max-h-[480px] overflow-y-auto divide-y divide-[var(--rl-border)]/70 rounded-lg border border-[var(--rl-border)] bg-[var(--rl-surface)] pr-1">
                {filteredAutoAssignMatches.length === 0 ? (
                  <div className="p-8 text-center text-xs text-[var(--rl-text-muted)]">
                    No benefit concepts match the current filter or search.
                  </div>
                ) : (
                  filteredAutoAssignMatches.map((m) => {
                    const currentAssetId = assignedOverrides[m.concept_id] || "";
                    const activeAsset = autoAssignData.available_category_assets.find((a) => a.id === currentAssetId);
                    const isAssigned = Boolean(currentAssetId);

                    return (
                      <div
                        key={m.concept_id}
                        className="p-3 flex items-center justify-between gap-4 text-xs hover:bg-[var(--rl-bg)]/60 transition-colors"
                      >
                        {/* Benefit info */}
                        <div className="min-w-0 flex items-center gap-3 flex-1">
                          <span className="px-2 py-1 rounded bg-[var(--rl-bg)] border border-[var(--rl-border)] text-[var(--rl-text-muted)] font-mono text-[11px] font-bold shrink-0">
                            #{String(m.sort_order).padStart(2, "0")}
                          </span>
                          <div className="min-w-0 flex-1">
                            <span className="font-bold text-[13px] text-[var(--rl-text-strong)] block truncate leading-tight">
                              {m.concept_label}
                            </span>
                            <div className="flex flex-wrap items-center gap-2 mt-1">
                              <span className="text-[11px] text-[var(--rl-text-muted)] font-mono">
                                {m.concept_key}
                              </span>
                              {isAssigned ? (
                                <span className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-700 bg-emerald-50 border border-emerald-200/80 px-1.5 py-0.5 rounded">
                                  🎯 {m.match_reason || "Assigned"}
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-[10px] font-medium text-amber-700 bg-amber-50 border border-amber-200/80 px-1.5 py-0.5 rounded">
                                  ⚠️ Unassigned
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* Thumbnail & Select override */}
                        <div className="flex items-center gap-2.5 shrink-0">
                          {activeAsset ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={fileUrl(activeAsset.url)}
                              alt={activeAsset.label}
                              className="h-11 w-11 object-contain rounded-lg border border-[var(--rl-border)] bg-white p-1 shadow-xs shrink-0"
                            />
                          ) : (
                            <div className="h-11 w-11 rounded-lg border border-dashed border-[var(--rl-border)] grid place-items-center text-[var(--rl-text-muted)] text-xs font-mono font-medium shrink-0 bg-[var(--rl-bg)]/50">
                              ?
                            </div>
                          )}

                          <Select
                            value={currentAssetId}
                            onChange={(e) => {
                              const nextVal = e.target.value;
                              setAssignedOverrides((prev) => {
                                const copy = { ...prev };
                                if (nextVal) {
                                  copy[m.concept_id] = nextVal;
                                } else {
                                  delete copy[m.concept_id];
                                }
                                return copy;
                              });
                            }}
                            className="w-64 sm:w-72 text-xs h-9 font-medium"
                          >
                            <option value="">(Unassigned / None)</option>
                            {autoAssignData.available_category_assets.map((a) => (
                              <option key={a.id} value={a.id}>
                                🖼️ {a.label || a.original_filename}
                              </option>
                            ))}
                          </Select>

                          {isAssigned && (
                            <button
                              type="button"
                              title="Unassign icon"
                              onClick={() => {
                                setAssignedOverrides((prev) => {
                                  const copy = { ...prev };
                                  delete copy[m.concept_id];
                                  return copy;
                                });
                              }}
                              className="h-8 w-8 rounded flex items-center justify-center text-[var(--rl-text-muted)] hover:text-red-600 hover:bg-red-50 border border-transparent hover:border-red-200 transition-colors"
                            >
                              <X size={14} />
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </>
          ) : (
            <PageLoading />
          )}
        </div>
      </Dialog>

      {/* --- MODAL 2: CLONE PROFILE --- */}
      <Dialog
        open={cloneProfileOpen}
        onOpenChange={setCloneProfileOpen}
        title="Clone Visual Profile"
        description={`Creates an exact copy of visual profile "${currentProfile?.name}" with all concept-asset mappings preserved.`}
        onConfirm={handleCloneProfileSubmit}
        confirmLabel={cloningProfile ? "Cloning..." : "Clone Profile"}
        loading={cloningProfile}
      >
        <div className="grid gap-3 text-xs">
          <label className="grid gap-1">
            <span className="font-bold text-[var(--rl-text-strong)]">New Profile Name</span>
            <Input
              value={cloneProfileName}
              onChange={(e) => setCloneProfileName(e.target.value)}
              placeholder="e.g. Minimal Line Art v2, gbv2..."
            />
          </label>

          <label className="grid gap-1">
            <span className="font-bold text-[var(--rl-text-strong)]">Asset Folder / Category</span>
            <Select
              value={cloneProfileCategory}
              onChange={(e) => setCloneProfileCategory(e.target.value)}
            >
              {assetCategories.map((c) => {
                const catName = c.category || (c as any).name || "General";
                return (
                  <option key={catName} value={catName}>
                    📁 {catName} ({c.count} assets)
                  </option>
                );
              })}
            </Select>
          </label>

          <label className="grid gap-1">
            <span className="font-bold text-[var(--rl-text-strong)]">Description (optional)</span>
            <Input
              value={cloneProfileDesc}
              onChange={(e) => setCloneProfileDesc(e.target.value)}
              placeholder="Profile notes..."
            />
          </label>
        </div>
      </Dialog>

      {/* --- MODAL 3: NEW PROFILE --- */}
      <Dialog
        open={newProfileOpen}
        onOpenChange={setNewProfileOpen}
        title="Create Visual Profile"
        description="Creates a new visual theme profile linked exclusively to one asset folder."
        onConfirm={handleCreateProfileSubmit}
        confirmLabel={creatingProfile ? "Creating..." : "Create Profile"}
        loading={creatingProfile}
      >
        <div className="grid gap-3 text-xs">
          <label className="grid gap-1">
            <span className="font-bold text-[var(--rl-text-strong)]">Profile Name</span>
            <Input
              value={newProfileName}
              onChange={(e) => setNewProfileName(e.target.value)}
              placeholder="e.g. Minimal Line Art v1, gbv1..."
              autoFocus
            />
          </label>

          <div className="grid gap-1">
            <span className="font-bold text-[var(--rl-text-strong)]">Target Asset Folder / Category</span>
            <Select
              value={newProfileCategory}
              onChange={(e) => setNewProfileCategory(e.target.value)}
            >
              {assetCategories.map((c) => {
                const catName = c.category || (c as any).name || "General";
                return (
                  <option key={catName} value={catName}>
                    📁 {catName} ({c.count} assets)
                  </option>
                );
              })}
              <option value="__new__">+ New folder / category...</option>
            </Select>
            {newProfileCategory === "__new__" ? (
              <Input
                placeholder="Enter folder name..."
                value={newProfileCustomCat}
                onChange={(e) => setNewProfileCustomCat(e.target.value)}
                className="mt-1"
              />
            ) : null}
          </div>

          <label className="grid gap-1">
            <span className="font-bold text-[var(--rl-text-strong)]">Description (optional)</span>
            <Input
              value={newProfileDesc}
              onChange={(e) => setNewProfileDesc(e.target.value)}
              placeholder="e.g. Clean monochromatic line art style..."
            />
          </label>
        </div>
      </Dialog>

      {/* Confirm Delete Concept Modal */}
      <ConfirmDialog
        open={showDeleteConfirm}
        onOpenChange={setShowDeleteConfirm}
        title="Move benefit to trash?"
        message={`Are you sure you want to move "${selected?.label}" to Trash? It can be restored later.`}
        confirmLabel={deleting ? "Deleting..." : "Move to Trash"}
        loading={deleting}
        onConfirm={handleDeleteConcept}
      />
    </AppShell>
  );
}
