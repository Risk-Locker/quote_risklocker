"use client";

import { useEffect, useMemo, useState } from "react";
import {
  BracketsCurly,
  CaretRight,
  Diamond,
  Eye,
  EyeSlash,
  FolderSimple,
  Image,
  LineSegment,
  LockSimple,
  LockSimpleOpen,
  Square,
  TextT,
  Triangle,
} from "@phosphor-icons/react";
import type { CanvasElement } from "@/components/template-canvas/shared";

export type LayerAction = "duplicate" | "delete" | "group" | "ungroup" | "lock" | "visibility" | "forward" | "backward" | "front" | "back";

type LayersPanelProps = {
  elements: CanvasElement[];
  selectedIds: Set<string>;
  readOnly: boolean;
  onSelect: (id: string, additive: boolean) => void;
  onRename: (id: string, name: string) => void;
  onToggleLock: (id: string) => void;
  onToggleVisibility: (id: string) => void;
  onNest: (id: string, groupId: string | null) => void;
  onReorder: (id: string, targetId: string, position: "before" | "after") => void;
  onAction: (action: LayerAction, id: string) => void;
};

function label(element: CanvasElement) {
  if (element.name) return element.name;
  if (element.type === "layer-group") return element.groupName || "Group";
  if (element.type === "text") return element.text?.trim().replace(/\s+/g, " ").slice(0, 36) || "Text";
  if (element.type === "variable") return element.variableId ? `Variable · ${element.variableId}` : "Variable";
  if (element.type === "benefit-grid") return element.gridKind === "available_addons" ? "Available Add-ons" : "Current Benefits";
  return element.type.replaceAll("-", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function LayerIcon({ element }: { element: CanvasElement }) {
  const common = { size: 14, weight: "bold" as const, className: "shrink-0 text-[var(--rl-text-muted)]" };
  if (element.type === "layer-group") return <FolderSimple {...common} />;
  if (element.type === "text") return <TextT {...common} />;
  if (element.type === "variable") return <BracketsCurly {...common} className="shrink-0 text-[var(--rl-red)]" />;
  if (element.type === "image") return <Image {...common} />;
  if (element.type === "line") return <LineSegment {...common} />;
  if (element.type === "triangle") return <Triangle {...common} />;
  if (element.type === "diamond") return <Diamond {...common} />;
  return <Square {...common} />;
}

export function LayersPanel({ elements, selectedIds, readOnly, onSelect, onRename, onToggleLock, onToggleVisibility, onNest, onReorder, onAction }: LayersPanelProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [dragging, setDragging] = useState<string | null>(null);
  const [menu, setMenu] = useState<{ id: string; x: number; y: number } | null>(null);

  useEffect(() => {
    if (!menu) return;
    const close = () => setMenu(null);
    window.addEventListener("pointerdown", close);
    window.addEventListener("blur", close);
    return () => { window.removeEventListener("pointerdown", close); window.removeEventListener("blur", close); };
  }, [menu]);

  const groups = useMemo(() => elements.filter((item) => item.type === "layer-group"), [elements]);
  const rootGroups = useMemo(() => groups.filter((item) => !item.parentId).sort((a, b) => (b.order ?? b.z ?? 0) - (a.order ?? a.z ?? 0)), [groups]);
  const rootLayers = useMemo(() => elements.filter((item) => item.type !== "layer-group" && !item.groupId).sort((a, b) => (b.z || 0) - (a.z || 0)), [elements]);

  function finishRename(element: CanvasElement) {
    const value = renameValue.trim();
    if (value && value !== label(element)) onRename(element.id, value);
    setRenaming(null);
  }

  function row(element: CanvasElement, depth: number) {
    const isGroup = element.type === "layer-group";
    const open = !collapsed.has(element.id);
    const selected = selectedIds.has(element.id);
    return (
      <div key={element.id}>
        <div
          draggable={!readOnly}
          onDragStart={(event) => { setDragging(element.id); event.dataTransfer.setData("application/risklocker-layer", element.id); event.dataTransfer.effectAllowed = "move"; }}
          onDragEnd={() => setDragging(null)}
          onDragOver={(event) => { if (!readOnly && dragging && dragging !== element.id) { event.preventDefault(); event.dataTransfer.dropEffect = "move"; } }}
          onDrop={(event) => {
            event.preventDefault();
            const sourceId = event.dataTransfer.getData("application/risklocker-layer");
            if (!sourceId || sourceId === element.id) return;
            const rect = event.currentTarget.getBoundingClientRect();
            const ratio = (event.clientY - rect.top) / rect.height;
            if (isGroup && ratio >= 0.25 && ratio <= 0.75) onNest(sourceId, element.id);
            else onReorder(sourceId, element.id, ratio < 0.5 ? "before" : "after");
          }}
          onContextMenu={(event) => { event.preventDefault(); if (!selectedIds.has(element.id)) onSelect(element.id, false); setMenu({ id: element.id, x: event.clientX, y: event.clientY }); }}
          className={`group flex h-8 items-center gap-1 border-l-2 pr-1 text-[12px] ${selected ? "border-[var(--rl-red)] bg-[var(--rl-red-light)]" : "border-transparent hover:bg-[var(--rl-bg)]"} ${dragging === element.id ? "opacity-50" : ""}`}
          style={{ paddingLeft: 5 + depth * 14 }}
        >
          {isGroup ? <button type="button" aria-label={open ? `Collapse ${label(element)}` : `Expand ${label(element)}`} className="grid h-6 w-5 place-items-center" onClick={() => setCollapsed((current) => { const next = new Set(current); if (next.has(element.id)) next.delete(element.id); else next.add(element.id); return next; })}><CaretRight size={12} weight="bold" className={open ? "rotate-90" : ""} /></button> : <span className="w-5" />}
          <button type="button" className="grid h-6 w-6 place-items-center" aria-label={element.visible === false ? `Show ${label(element)}` : `Hide ${label(element)}`} disabled={readOnly} onClick={() => onToggleVisibility(element.id)}>{element.visible === false ? <EyeSlash size={14} /> : <Eye size={14} />}</button>
          <button type="button" className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={(event) => onSelect(element.id, event.shiftKey)} onDoubleClick={() => { if (!readOnly) { setRenaming(element.id); setRenameValue(label(element)); } }}>
            <LayerIcon element={element} />
            {renaming === element.id ? <input autoFocus value={renameValue} onChange={(event) => setRenameValue(event.target.value)} onClick={(event) => event.stopPropagation()} onBlur={() => finishRename(element)} onKeyDown={(event) => { if (event.key === "Enter") finishRename(element); if (event.key === "Escape") setRenaming(null); }} className="h-6 min-w-0 flex-1 border border-[var(--rl-red)] bg-white px-1 outline-none" /> : <span className="truncate font-medium text-[var(--rl-text-strong)]">{label(element)}</span>}
          </button>
          <button type="button" className="grid h-6 w-6 place-items-center opacity-50 group-hover:opacity-100" aria-label={element.locked ? `Unlock ${label(element)}` : `Lock ${label(element)}`} disabled={readOnly} onClick={() => onToggleLock(element.id)}>{element.locked ? <LockSimple size={14} weight="fill" /> : <LockSimpleOpen size={14} />}</button>
        </div>
        {isGroup && open ? (
          <div>
            {groups.filter((child) => child.parentId === element.id).sort((a, b) => (b.order ?? 0) - (a.order ?? 0)).map((child) => row(child, depth + 1))}
            {elements.filter((child) => child.type !== "layer-group" && child.groupId === element.id).sort((a, b) => (b.z || 0) - (a.z || 0)).map((child) => row(child, depth + 1))}
          </div>
        ) : null}
      </div>
    );
  }

  const target = menu ? elements.find((item) => item.id === menu.id) : null;
  const actions: Array<{ action: LayerAction; label: string; enabled: boolean }> = [
    { action: "duplicate", label: "Duplicate", enabled: Boolean(target && target.type !== "benefit-grid") },
    { action: "group", label: "Group selection", enabled: selectedIds.size >= 2 },
    { action: "ungroup", label: "Ungroup", enabled: target?.type === "layer-group" },
    { action: "lock", label: target?.locked ? "Unlock" : "Lock", enabled: Boolean(target) },
    { action: "visibility", label: target?.visible === false ? "Show" : "Hide", enabled: Boolean(target) },
    { action: "forward", label: "Bring forward", enabled: target?.type !== "layer-group" },
    { action: "backward", label: "Send backward", enabled: target?.type !== "layer-group" },
    { action: "front", label: "Move to front", enabled: target?.type !== "layer-group" },
    { action: "back", label: "Move to back", enabled: target?.type !== "layer-group" },
    { action: "delete", label: "Delete", enabled: Boolean(target) },
  ];

  return (
    <section aria-label="Template layers" className="grid h-full min-h-0 grid-rows-[auto_1fr]">
      <div className="border-b border-[var(--rl-border)] px-3 py-3"><h2 className="m-0 text-[12px] font-bold uppercase tracking-[0.12em] text-[var(--rl-text-muted)]">Layers</h2><p className="mt-1 text-[11px] text-[var(--rl-text-muted)]">Top rows render on top. Shift-click selects several.</p></div>
      <div className="min-h-0 overflow-y-auto py-2" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { const sourceId = event.dataTransfer.getData("application/risklocker-layer"); if (sourceId) onNest(sourceId, null); }}>
        {rootGroups.map((group) => row(group, 0))}
        {rootLayers.map((element) => row(element, 0))}
        {!elements.length ? <p className="p-4 text-[12px] text-[var(--rl-text-muted)]">This page has no layers.</p> : null}
      </div>
      {menu && target ? <div role="menu" className="fixed z-[100] min-w-48 border border-[var(--rl-border)] bg-white py-1 shadow-lift" style={{ left: Math.min(menu.x, window.innerWidth - 210), top: Math.min(menu.y, window.innerHeight - 360) }} onPointerDown={(event) => event.stopPropagation()}>{actions.map((item) => <button key={item.action} role="menuitem" type="button" disabled={readOnly || !item.enabled} className={`block w-full px-3 py-2 text-left text-[12px] font-medium hover:bg-[var(--rl-bg)] disabled:opacity-35 ${item.action === "delete" ? "text-[var(--rl-red)]" : "text-[var(--rl-text-strong)]"}`} onClick={() => { setMenu(null); onAction(item.action, target.id); }}>{item.label}</button>)}</div> : null}
    </section>
  );
}
