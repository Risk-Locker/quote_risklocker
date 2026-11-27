"use client";

import React, { useMemo, useState } from "react";
import {
  ChatCircleText,
  MagnifyingGlass,
  PencilSimple,
  Plus,
  PushPin,
  Trash,
  Check,
  X,
} from "@phosphor-icons/react";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { CopilotThread } from "./types";

type CopilotInboxSidebarProps = {
  threads: CopilotThread[];
  activeThreadId: string | null;
  loading: boolean;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onSelectThread: (id: string) => void;
  onNewChat: () => void;
  onRenameThread: (id: string, title: string) => Promise<void>;
  onTogglePin: (id: string, pinned: boolean) => Promise<void>;
  onDeleteThread: (id: string) => Promise<void>;
};

function bucketThreadDate(iso?: string | null): "Today" | "Yesterday" | "Last 7 Days" | "Older" {
  if (!iso) return "Older";
  const d = new Date(iso);
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const ts = d.getTime();
  if (ts >= startToday) return "Today";
  if (ts >= startToday - 86_400_000) return "Yesterday";
  if (ts >= startToday - 7 * 86_400_000) return "Last 7 Days";
  return "Older";
}

export function CopilotInboxSidebar({
  threads,
  activeThreadId,
  loading,
  searchQuery,
  onSearchChange,
  onSelectThread,
  onNewChat,
  onRenameThread,
  onTogglePin,
  onDeleteThread,
}: CopilotInboxSidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<CopilotThread | null>(null);
  const [deleting, setDeleting] = useState(false);

  const grouped = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const filtered = q
      ? threads.filter(
          (t) =>
            t.title.toLowerCase().includes(q) ||
            (t.anchor_label || "").toLowerCase().includes(q)
        )
      : threads;

    const pinned = filtered.filter((t) => t.is_pinned);
    const unpinned = filtered.filter((t) => !t.is_pinned);
    const buckets: Record<"Today" | "Yesterday" | "Last 7 Days" | "Older", CopilotThread[]> = {
      Today: [],
      Yesterday: [],
      "Last 7 Days": [],
      Older: [],
    };
    for (const t of unpinned) {
      buckets[bucketThreadDate(t.last_message_at || t.updated_at)].push(t);
    }
    return { pinned, buckets };
  }, [threads, searchQuery]);

  async function saveRename(id: string) {
    const trimmed = editingTitle.trim();
    if (trimmed) {
      await onRenameThread(id, trimmed);
    }
    setEditingId(null);
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await onDeleteThread(deleteTarget.id);
      setDeleteTarget(null);
    } finally {
      setDeleting(false);
    }
  }

  function renderThreadRow(t: CopilotThread) {
    const isActive = t.id === activeThreadId;
    const isEditing = editingId === t.id;

    return (
      <div
        key={t.id}
        className={`group relative rounded-[var(--rl-radius-sm)] px-2.5 py-2 text-xs transition-colors cursor-pointer ${
          isActive
            ? "bg-[var(--rl-black)] text-white"
            : "text-[var(--rl-text)] hover:bg-neutral-100"
        }`}
        onClick={() => {
          if (!isEditing) onSelectThread(t.id);
        }}
      >
        {isEditing ? (
          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            <input
              type="text"
              value={editingTitle}
              onChange={(e) => setEditingTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveRename(t.id);
                if (e.key === "Escape") setEditingId(null);
              }}
              autoFocus
              className="flex-1 rounded border border-neutral-300 bg-white px-1.5 py-0.5 text-[11px] text-neutral-900 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => saveRename(t.id)}
              className="p-1 text-emerald-500 hover:text-emerald-600 cursor-pointer"
              aria-label="Save title"
            >
              <Check size={12} weight="bold" />
            </button>
            <button
              type="button"
              onClick={() => setEditingId(null)}
              className="p-1 text-neutral-400 hover:text-neutral-600 cursor-pointer"
              aria-label="Cancel rename"
            >
              <X size={12} weight="bold" />
            </button>
          </div>
        ) : (
          <div className="flex items-start justify-between gap-1.5">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                {t.is_pinned && (
                  <PushPin
                    size={11}
                    weight="fill"
                    className={isActive ? "text-amber-300 shrink-0" : "text-amber-600 shrink-0"}
                  />
                )}
                <span className="truncate font-medium text-[12px]">{t.title}</span>
              </div>
              {t.anchor_label && (
                <div
                  className={`mt-0.5 truncate text-[10px] ${
                    isActive ? "text-neutral-300" : "text-[var(--rl-text-muted)]"
                  }`}
                >
                  {t.anchor_label}
                </div>
              )}
            </div>

            <div
              className={`flex items-center gap-0.5 shrink-0 ${
                isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100"
              } transition-opacity`}
              onClick={(e) => e.stopPropagation()}
            >
              <button
                type="button"
                onClick={() => onTogglePin(t.id, !t.is_pinned)}
                title={t.is_pinned ? "Unpin" : "Pin"}
                className={`p-1 rounded cursor-pointer ${
                  isActive ? "hover:bg-white/15 text-neutral-200" : "hover:bg-neutral-200 text-neutral-500"
                }`}
              >
                <PushPin size={12} weight={t.is_pinned ? "fill" : "regular"} />
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditingId(t.id);
                  setEditingTitle(t.title);
                }}
                title="Rename"
                className={`p-1 rounded cursor-pointer ${
                  isActive ? "hover:bg-white/15 text-neutral-200" : "hover:bg-neutral-200 text-neutral-500"
                }`}
              >
                <PencilSimple size={12} />
              </button>
              <button
                type="button"
                onClick={() => setDeleteTarget(t)}
                title="Delete"
                className={`p-1 rounded cursor-pointer ${
                  isActive ? "hover:bg-white/15 text-rose-300" : "hover:bg-rose-50 text-rose-600"
                }`}
              >
                <Trash size={12} />
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col border-r border-[var(--rl-border)] bg-neutral-50/70">
      <div className="p-3 border-b border-[var(--rl-border)] space-y-2">
        <Button
          type="button"
          size="sm"
          onClick={onNewChat}
          className="w-full h-8 text-xs justify-center gap-1.5"
          icon={<Plus size={13} weight="bold" />}
        >
          New Chat
        </Button>
        <div className="relative">
          <MagnifyingGlass
            size={13}
            className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]"
          />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search chat history..."
            className="w-full rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white pl-7 pr-2.5 py-1.5 text-[11px] text-[var(--rl-text-strong)] placeholder:text-[var(--rl-text-muted)] focus:outline-none focus:border-[var(--rl-black)]"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-3">
        {loading && threads.length === 0 ? (
          <div className="p-3 text-center text-[11px] text-[var(--rl-text-muted)]">Loading sessions...</div>
        ) : null}

        {grouped.pinned.length > 0 && (
          <div className="space-y-0.5">
            <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
              Pinned
            </div>
            {grouped.pinned.map(renderThreadRow)}
          </div>
        )}

        {(["Today", "Yesterday", "Last 7 Days", "Older"] as const).map((label) => {
          const list = grouped.buckets[label];
          if (!list.length) return null;
          return (
            <div key={label} className="space-y-0.5">
              <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-[var(--rl-text-muted)]">
                {label}
              </div>
              {list.map(renderThreadRow)}
            </div>
          );
        })}

        {!loading && threads.length === 0 && (
          <div className="p-4 text-center space-y-1.5 text-[var(--rl-text-muted)]">
            <ChatCircleText size={20} className="mx-auto opacity-60" />
            <p className="text-[11px]">No saved conversations yet.</p>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={!!deleteTarget}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete Chat Session"
        message={`Delete "${deleteTarget?.title || "this chat"}"? This removes it from your inbox.`}
        confirmLabel="Delete"
        loading={deleting}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
