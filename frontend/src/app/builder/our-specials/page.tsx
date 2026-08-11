"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, FloppyDisk, Image, PencilSimple, Plus, Trash, X } from "@phosphor-icons/react";
import { BuilderNav } from "@/components/builder-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api, fileUrl } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type Variant = {
  id: string;
  special_id: string;
  label: string;
  secondary_label?: string | null;
  value_text?: string | null;
  icon_asset_id?: string | null;
  shape?: string | null;
  bg_color?: string | null;
  text_color?: string | null;
  border_width?: string | null;
  border_color?: string | null;
  shadow?: string | null;
  status: string;
};

type OurSpecial = {
  id: string;
  label: string;
  category: string;
  status: string;
  variants: Variant[];
};

type Asset = {
  id: string;
  label: string;
  url: string;
  filename: string;
  source: string;
};

const shapeRadii: Record<string, string> = {
  rounded: "12px",
  capsule: "999px",
  square: "0",
};

const shadowMap: Record<string, string> = {
  none: "none",
  sm: "0 1px 3px rgba(0,0,0,0.12)",
  md: "0 4px 12px rgba(0,0,0,0.15)",
  lg: "0 8px 24px rgba(0,0,0,0.18)",
};

const colorPresets = [
  "#FFFFFF", "#F6F8FB", "#FFF3E0", "#E8F5E9", "#E3F2FD", "#FCE4EC",
  "#1B1717", "#454545", "#ED1C24", "#0084FF", "#2F7D32", "#8A5A00",
];

function colorSwatches(value: string, onChange: (v: string) => void) {
  return (
    <div className="grid gap-1.5">
      <div className="flex flex-wrap gap-1">
        {colorPresets.map((c) => (
          <button
            key={c}
            type="button"
            className={`h-6 w-6 rounded border transition-all ${value === c ? "border-[var(--rl-black)] ring-2 ring-[var(--rl-black)]" : "border-[var(--rl-border)]"}`}
            style={{ backgroundColor: c }}
            onClick={() => onChange(c)}
            title={c}
          />
        ))}
      </div>
      <Input
        className="text-xs"
        placeholder="#FF0000"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

const SPECIAL_CATEGORIES = ["FOC", "Add-on"] as const;

function CategoryToggle({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="grid grid-cols-2 gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-1">
      {SPECIAL_CATEGORIES.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          className={`rounded-[var(--rl-radius-sm)] px-3 py-1.5 text-[13px] font-bold transition-all ${
            value === option ? "bg-[var(--rl-black)] text-white shadow-card" : "text-[var(--rl-text-muted)] hover:bg-[var(--rl-surface)]"
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

function VariantCard({
  variant,
  onEdit,
  onDelete,
}: {
  variant: Variant;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const radius = variant.shape ? (shapeRadii[variant.shape] || "12px") : "12px";
  const bg = variant.bg_color || "#FFFFFF";
  const tc = variant.text_color || "#1B1717";
  const borderW = variant.border_width && variant.border_width !== "none" ? variant.border_width : undefined;
  const borderC = variant.border_color || "transparent";
  const sh = variant.shadow ? (shadowMap[variant.shadow] || "none") : "none";

  return (
    <div
      className="relative flex flex-col items-center gap-1.5 p-3 transition-transform hover:scale-[1.02]"
      style={{
        borderRadius: radius,
        backgroundColor: bg,
        color: tc,
        border: borderW ? `${borderW} solid ${borderC}` : undefined,
        boxShadow: sh,
        minWidth: 150,
      }}
    >
      <div className="absolute right-1 top-1 flex gap-1">
        <button type="button" className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-black/10" onClick={onEdit} title="Edit">
          <PencilSimple weight="bold" size={12} />
        </button>
        <button type="button" className="rounded p-1 text-[var(--rl-text-muted)] hover:bg-black/10" onClick={onDelete} title="Delete">
          <Trash weight="bold" size={12} />
        </button>
      </div>
      {variant.icon_asset_id ? (
        <img
          src={fileUrl(`/template-assets/${variant.icon_asset_id}`)}
          alt=""
          className="h-10 w-10 object-contain"
        />
      ) : (
        <div className="flex h-10 w-10 items-center justify-center rounded border border-[var(--rl-border)] bg-[var(--rl-bg)] text-[10px] text-[var(--rl-text-muted)]">
          <Image weight="bold" size={14} />
        </div>
      )}
      <span className="text-center text-xs font-bold leading-tight">{variant.label}</span>
      {variant.secondary_label ? (
        <span className="text-center text-[10px] leading-tight" style={{ opacity: 0.7 }}>{variant.secondary_label}</span>
      ) : null}
      {variant.value_text ? (
        <span className="text-center text-[11px] font-bold">{variant.value_text}</span>
      ) : null}
    </div>
  );
}

const emptyVariant: Variant = {
  id: "",
  special_id: "",
  label: "",
  secondary_label: "",
  value_text: "",
  icon_asset_id: "",
  shape: "rounded",
  bg_color: "#F6F8FB",
  text_color: "#1B1717",
  border_width: "1px",
  border_color: "#D8DDE6",
  shadow: "none",
  status: "active",
};

export default function BuilderOurSpecialsPage() {
  const [specials, setSpecials] = useState<OurSpecial[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pendingDeleteSpecial, setPendingDeleteSpecial] = useState<OurSpecial | null>(null);
  const [pendingDeleteVariant, setPendingDeleteVariant] = useState<Variant | null>(null);
  const [showCreateSpecial, setShowCreateSpecial] = useState(false);
  const [createLabel, setCreateLabel] = useState("");
  const [createCategory, setCreateCategory] = useState("FOC");
  const [editingVariant, setEditingVariant] = useState<Variant>({ ...emptyVariant });
  const [showAssetPicker, setShowAssetPicker] = useState(false);
  const { toast } = useToast();

  async function load() {
    const result = await api<{ our_specials: OurSpecial[] }>("/admin/our-specials");
    setSpecials(result.our_specials);
    if (selectedId && !result.our_specials.find((s) => s.id === selectedId)) {
      setSelectedId(null);
    }
  }

  async function loadAssets() {
    try {
      const result = await api<{ assets: Asset[] }>("/admin/template-assets");
      setAssets(result.assets);
    } catch {
      setAssets([]);
    }
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load our specials."));
    loadAssets();
  }, []);

  async function createSpecial(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/admin/our-specials", {
        method: "POST",
        body: JSON.stringify({ label: createLabel, category: createCategory }),
      });
      setCreateLabel("");
      setShowCreateSpecial(false);
      toast("Special created.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function deleteSpecial(special: OurSpecial) {
    setError("");
    try {
      await api(`/admin/our-specials/${special.id}`, { method: "DELETE" });
      if (selectedId === special.id) {
        setSelectedId(null);
        setEditingVariant({ ...emptyVariant });
      }
      toast(`"${special.label}" deleted.`, "success");
      setPendingDeleteSpecial(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete special.");
    }
    await load();
  }

  async function updateSpecial(special: OurSpecial, payload: { label?: string; category?: string }) {
    setError("");
    try {
      await api("/admin/our-specials", {
        method: "POST",
        body: JSON.stringify({ id: special.id, ...payload }),
      });
      toast("Special updated.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function saveVariant(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const payload: Record<string, unknown> = {
        special_id: selectedId,
        label: editingVariant.label,
        secondary_label: editingVariant.secondary_label || null,
        value_text: editingVariant.value_text || null,
        icon_asset_id: editingVariant.icon_asset_id || null,
        shape: editingVariant.shape || null,
        bg_color: editingVariant.bg_color || null,
        text_color: editingVariant.text_color || null,
        border_width: editingVariant.border_width || null,
        border_color: editingVariant.border_color || null,
        shadow: editingVariant.shadow || null,
        status: editingVariant.status,
      };
      if (editingVariant.id) {
        payload.id = editingVariant.id;
      }
      await api("/admin/our-special-variants", { method: "POST", body: JSON.stringify(payload) });
      setEditingVariant({ ...emptyVariant, special_id: selectedId || "" });
      setShowAssetPicker(false);
      toast("Variant saved.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function deleteVariant(variant: Variant) {
    setError("");
    try {
      await api(`/admin/our-special-variants/${variant.id}`, { method: "DELETE" });
      toast("Variant deleted.", "success");
      setPendingDeleteVariant(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete variant.");
    }
    await load();
  }

  function startEdit(variant: Variant) {
    setEditingVariant({
      ...variant,
      shape: variant.shape || "rounded",
      bg_color: variant.bg_color || "#F6F8FB",
      text_color: variant.text_color || "#1B1717",
      border_width: variant.border_width || "none",
      border_color: variant.border_color || "#D8DDE6",
      shadow: variant.shadow || "none",
    });
    setShowAssetPicker(false);
  }

  function startCreate() {
    setEditingVariant({ ...emptyVariant, special_id: selectedId || "" });
    setShowAssetPicker(false);
  }

  const selected = specials.find((s) => s.id === selectedId);
  const focSpecials = specials.filter((s) => s.category === "FOC");
  const addOnSpecials = specials.filter((s) => s.category === "Add-on");

  const previewVariant = useMemo(() => ({
    ...editingVariant,
    id: "preview",
  }), [editingVariant]);

  const isEditing = editingVariant.label !== "" || editingVariant.id !== "";

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)] mt-0">Our Specials</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">Design variant cards. Select a special on the left, then create or edit its variants.</p>
          </div>
        </div>
        <BuilderNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[260px_1fr_340px]">
          <aside className="grid gap-4 content-start">
            <Button
              icon={<Plus weight="bold" size={16} />}
              className="w-full"
              onClick={() => setShowCreateSpecial((v) => !v)}
            >
              New special
            </Button>

            {showCreateSpecial ? (
              <Card>
                <form className="grid gap-4 p-4" onSubmit={createSpecial}>
                  <div className="grid gap-1.5">
                    <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Label</label>
                    <Input placeholder="Label" value={createLabel} onChange={(e) => setCreateLabel(e.target.value)} required />
                  </div>
                  <div className="grid gap-1.5">
                    <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Category</label>
                    <CategoryToggle value={createCategory} onChange={setCreateCategory} />
                  </div>
                  <div className="flex gap-2">
                    <Button type="submit" size="sm" icon={<FloppyDisk weight="bold" size={14} />}>Save</Button>
                    <Button variant="secondary" size="sm" icon={<X weight="bold" size={14} />} onClick={() => setShowCreateSpecial(false)}>Cancel</Button>
                  </div>
                </form>
              </Card>
            ) : null}

            <SpecialList title="FOC" items={focSpecials} selectedId={selectedId} onSelect={setSelectedId} onDelete={setPendingDeleteSpecial} onUpdate={updateSpecial} />
            <SpecialList title="Add-on" items={addOnSpecials} selectedId={selectedId} onSelect={setSelectedId} onDelete={setPendingDeleteSpecial} onUpdate={updateSpecial} />
          </aside>

          <div className="grid gap-4 content-start">
            {selected ? (
              <>
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-bold text-[var(--rl-text-strong)]">
                    {selected.label}{" "}
                    <Badge variant="info">{selected.category}</Badge>
                  </h2>
                  <Button icon={<Plus weight="bold" size={14} />} size="sm" onClick={startCreate}>
                    Add variant
                  </Button>
                </div>
                {selected.variants.length ? (
                  <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(170px, 1fr))" }}>
                    {selected.variants.map((v) => (
                      <VariantCard key={v.id} variant={v} onEdit={() => startEdit(v)} onDelete={() => setPendingDeleteVariant(v)} />
                    ))}
                  </div>
                ) : (
                  <Card>
                    <div className="grid place-content-center p-10 text-center">
                      <p className="text-[14px] text-[var(--rl-text-muted)]">No variants yet. Click &ldquo;Add variant&rdquo; to create one.</p>
                    </div>
                  </Card>
                )}
              </>
            ) : (
              <Card>
                <div className="grid place-content-center p-10 text-center">
                  <p className="text-[14px] text-[var(--rl-text-muted)]">Select a special from the left to manage its variants.</p>
                </div>
              </Card>
            )}
          </div>

          {pendingDeleteSpecial ? (
            <ConfirmDialog
              open
              onOpenChange={(open) => { if (!open) setPendingDeleteSpecial(null); }}
              title={`Delete "${pendingDeleteSpecial.label}"?`}
              message="This deletes all its variants too. It moves to Trash and can be restored later."
              onConfirm={() => deleteSpecial(pendingDeleteSpecial)}
            />
          ) : null}

          {pendingDeleteVariant ? (
            <ConfirmDialog
              open
              onOpenChange={(open) => { if (!open) setPendingDeleteVariant(null); }}
              title={`Delete variant "${pendingDeleteVariant.label}"?`}
              message="It moves to Trash and can be restored later."
              onConfirm={() => deleteVariant(pendingDeleteVariant)}
            />
          ) : null}

          <aside className="grid gap-4 content-start">
            {isEditing ? (
              <Card>
                <form className="grid gap-4 p-4" onSubmit={saveVariant}>
                  <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">{editingVariant.id ? "Edit variant" : "New variant"}</h2>

                  <div className="grid gap-1.5">
                    <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Icon</label>
                    <button
                      type="button"
                      className="min-h-[40px] w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-surface)] px-3 py-2 text-[14px] text-[var(--rl-text-strong)] hover:border-[var(--rl-text-muted)] transition-colors flex items-center gap-2 text-left"
                      onClick={() => setShowAssetPicker(!showAssetPicker)}
                    >
                      {editingVariant.icon_asset_id ? (
                        <img src={fileUrl(`/template-assets/${editingVariant.icon_asset_id}`)} alt="" className="h-8 w-8 object-contain" />
                      ) : (
                        <Image weight="bold" size={16} />
                      )}
                      {editingVariant.icon_asset_id ? "Change icon" : "Pick an icon"}
                    </button>
                    {showAssetPicker ? (
                      <div className="mt-1 grid max-h-48 gap-1 overflow-auto rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-[var(--rl-bg)] p-2" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(48px, 1fr))" }}>
                        {assets.map((a) => (
                          <button
                            key={a.id}
                            type="button"
                            className={`flex h-12 w-12 items-center justify-center rounded border bg-[var(--rl-surface)] transition-all ${editingVariant.icon_asset_id === a.id ? "border-[var(--rl-black)] ring-2 ring-[var(--rl-black)]" : "border-[var(--rl-border)] hover:bg-[var(--rl-bg)]"}`}
                            onClick={() => {
                              setEditingVariant((v) => ({ ...v, icon_asset_id: a.id }));
                              setShowAssetPicker(false);
                            }}
                            title={a.label}
                          >
                            <img src={fileUrl(a.url)} alt={a.label} className="h-8 w-8 object-contain" />
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="grid gap-1.5">
                    <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Label</label>
                    <Input value={editingVariant.label} onChange={(e) => setEditingVariant((v) => ({ ...v, label: e.target.value }))} required />
                  </div>

                  <div className="grid gap-1.5">
                    <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Secondary label</label>
                    <Input placeholder="e.g. Windscreen Coverage" value={editingVariant.secondary_label || ""} onChange={(e) => setEditingVariant((v) => ({ ...v, secondary_label: e.target.value }))} />
                  </div>

                  <div className="grid gap-1.5">
                    <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Value text</label>
                    <Input placeholder="e.g. Up to RM 1,000" value={editingVariant.value_text || ""} onChange={(e) => setEditingVariant((v) => ({ ...v, value_text: e.target.value }))} />
                  </div>

                  <div className="grid gap-1.5">
                    <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Shape</label>
                    <Select value={editingVariant.shape || "rounded"} onChange={(e) => setEditingVariant((v) => ({ ...v, shape: e.target.value }))}>
                      <option value="rounded">Rounded</option>
                      <option value="capsule">Capsule</option>
                      <option value="square">Square</option>
                    </Select>
                  </div>

                  <fieldset className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-3">
                    <legend className="text-[13px] font-semibold text-[var(--rl-text-strong)] px-1">Background color</legend>
                    {colorSwatches(editingVariant.bg_color || "#FFFFFF", (c) => setEditingVariant((v) => ({ ...v, bg_color: c })))}
                  </fieldset>

                  <fieldset className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-3">
                    <legend className="text-[13px] font-semibold text-[var(--rl-text-strong)] px-1">Text color</legend>
                    {colorSwatches(editingVariant.text_color || "#1B1717", (c) => setEditingVariant((v) => ({ ...v, text_color: c })))}
                  </fieldset>

                  <div className="grid gap-1.5">
                    <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Border width</label>
                    <Select value={editingVariant.border_width || "none"} onChange={(e) => setEditingVariant((v) => ({ ...v, border_width: e.target.value }))}>
                      <option value="none">None</option>
                      <option value="1px">1px</option>
                      <option value="2px">2px</option>
                      <option value="3px">3px</option>
                    </Select>
                  </div>

                  <fieldset className="grid gap-2 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] p-3">
                    <legend className="text-[13px] font-semibold text-[var(--rl-text-strong)] px-1">Border color</legend>
                    {colorSwatches(editingVariant.border_color || "#D8DDE6", (c) => setEditingVariant((v) => ({ ...v, border_color: c })))}
                  </fieldset>

                  <div className="grid gap-1.5">
                    <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Shadow</label>
                    <Select value={editingVariant.shadow || "none"} onChange={(e) => setEditingVariant((v) => ({ ...v, shadow: e.target.value }))}>
                      <option value="none">None</option>
                      <option value="sm">Small</option>
                      <option value="md">Medium</option>
                      <option value="lg">Large</option>
                    </Select>
                  </div>

                  <div className="grid gap-1.5">
                    <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Move to special</label>
                    <Select
                      value=""
                      disabled={!editingVariant.id}
                      onChange={async (e) => {
                        const targetId = e.target.value;
                        if (!targetId || !editingVariant.id) return;
                        setError("");
                        try {
                          await api(`/admin/our-special-variants/${editingVariant.id}/move`, { method: "POST", body: JSON.stringify({ special_id: targetId }) });
                          toast("Variant moved.", "success");
                          setEditingVariant({ ...emptyVariant });
                          setSelectedId(targetId);
                          await load();
                        } catch (err) {
                          setError(apiErrorMessage(err));
                        }
                      }}
                    >
                      <option value="">{editingVariant.id ? "Move to another special…" : "Save the variant first"}</option>
                      {specials.filter((s) => s.id !== selectedId).map((s) => (
                        <option key={s.id} value={s.id}>{s.label}</option>
                      ))}
                    </Select>
                  </div>

                  <div className="flex gap-2">
                    <Button type="submit" icon={<FloppyDisk weight="bold" size={14} />} size="sm">Save</Button>
                    <Button variant="secondary" size="sm" icon={<X weight="bold" size={14} />} onClick={() => setEditingVariant({ ...emptyVariant })}>Cancel</Button>
                  </div>
                </form>
              </Card>
            ) : null}

            {isEditing ? (
              <Card>
                <div className="grid gap-3 p-4">
                  <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Preview</h2>
                  <div className="flex justify-center">
                    <VariantCard variant={previewVariant} onEdit={() => {}} onDelete={() => {}} />
                  </div>
                </div>
              </Card>
            ) : null}
          </aside>
        </div>
      </section>
    </AppShell>
  );
}

function SpecialList({
  title,
  items,
  selectedId,
  onSelect,
  onDelete,
  onUpdate,
}: {
  title: string;
  items: OurSpecial[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onDelete: (special: OurSpecial) => void;
  onUpdate: (special: OurSpecial, payload: { label?: string; category?: string }) => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState("");
  const [editCategory, setEditCategory] = useState("");

  if (!items.length) return null;

  function startEdit(item: OurSpecial) {
    setEditingId(item.id);
    setEditLabel(item.label);
    setEditCategory(item.category);
  }

  function cancelEdit() {
    setEditingId(null);
  }

  function saveEdit(item: OurSpecial) {
    onUpdate(item, { label: editLabel, category: editCategory });
    setEditingId(null);
  }

  return (
    <div className="grid gap-1">
      <h3 className="text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">{title}</h3>
      {items.map((item) => (
        <div
          key={item.id}
          className={`grid grid-cols-[1fr_auto] items-center gap-2 rounded-[var(--rl-radius-sm)] border p-2.5 text-[14px] cursor-pointer transition-all ${
            selectedId === item.id
              ? "border-[var(--rl-black)] bg-[var(--rl-black)] text-white"
              : "border-[var(--rl-border)] bg-[var(--rl-surface)] text-[var(--rl-text-strong)] hover:bg-[var(--rl-bg)]"
          }`}
          onClick={() => onSelect(item.id)}
        >
          {editingId === item.id ? (
            <div className="col-span-2 grid gap-2 p-1" onClick={(e) => e.stopPropagation()}>
              <Input value={editLabel} onChange={(e) => setEditLabel(e.target.value)} placeholder="Label" />
              <CategoryToggle value={editCategory} onChange={setEditCategory} />
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  icon={<FloppyDisk weight="bold" size={14} />}
                  onClick={() => saveEdit(item)}
                >
                  Save
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<X weight="bold" size={14} />}
                  onClick={cancelEdit}
                >
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex items-center gap-1.5">
                {selectedId === item.id ? (
                  <Check weight="bold" size={14} className="text-white" />
                ) : null}
                <span className="font-bold">{item.label}</span>
                <span className={`text-xs ${selectedId === item.id ? "text-white/60" : "text-[var(--rl-text-muted)]"}`}>
                  {item.variants.length}
                </span>
                <button
                  type="button"
                  className={`rounded p-1 transition-colors ${
                    selectedId === item.id
                      ? "text-white/60 hover:text-white"
                      : "text-[var(--rl-text-muted)] hover:text-[var(--rl-black)]"
                  }`}
                  onClick={(e) => { e.stopPropagation(); startEdit(item); }}
                  title="Edit"
                >
                  <PencilSimple weight="bold" size={14} />
                </button>
              </div>
              <button
                type="button"
                className={`rounded p-1 transition-colors ${
                  selectedId === item.id
                    ? "text-white/60 hover:text-white"
                    : "text-[var(--rl-text-muted)] hover:text-[var(--rl-red)]"
                }`}
                onClick={(e) => { e.stopPropagation(); onDelete(item); }}
                title="Delete"
              >
                <Trash weight="bold" size={14} />
              </button>
            </>
          )}
        </div>
      ))}
    </div>
  );
}
