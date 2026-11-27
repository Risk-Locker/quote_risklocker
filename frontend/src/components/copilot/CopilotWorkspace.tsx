"use client";

import React, { useState } from "react";
import Link from "next/link";
import type { Route } from "next";
import {
  ArrowsInSimple,
  ArrowsOutSimple,
  ArrowSquareOut,
  Plus,
  Robot,
  SidebarSimple,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { Badge } from "@/components/ui/badge";
import { useCopilot } from "./CopilotProvider";
import { CopilotInboxSidebar } from "./CopilotInboxSidebar";
import { CopilotMessageStream } from "./CopilotMessageStream";
import { CopilotComposer } from "./CopilotComposer";
import { CopilotArtifactPane } from "./CopilotArtifactPane";

type CopilotWorkspaceProps = {
  variant: "sidecar" | "fullscreen";
  onCloseDrawer?: () => void;
};

export function CopilotWorkspace({ variant, onCloseDrawer }: CopilotWorkspaceProps) {
  const {
    drawerMode,
    setDrawerMode,
    threads,
    threadsLoading,
    threadSearch,
    setThreadSearch,
    activeThreadId,
    activeThread,
    messages,
    messagesLoading,
    streaming,
    error,
    clearError,
    quota,
    pageContext,
    contextPinned,
    setContextPinned,
    activeArtifact,
    setActiveArtifact,
    selectThread,
    createNewThread,
    renameThread,
    togglePinThread,
    deleteThread,
    sendMessage,
    stopStreaming,
    submitFeedback,
  } = useCopilot();

  const [showInboxInSidecar, setShowInboxInSidecar] = useState(variant === "fullscreen");
  const [externalDraft, setExternalDraft] = useState<string>("");

  const showSidebar = variant === "fullscreen" || drawerMode === "wide" || showInboxInSidecar;

  return (
    <div className="flex h-full w-full flex-col bg-white text-[var(--rl-text-strong)] overflow-hidden">
      {/* Top Bar */}
      <div className="flex items-center justify-between gap-2 border-b border-[var(--rl-border)] px-3.5 py-2.5 bg-white shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <button
            type="button"
            onClick={() => setShowInboxInSidecar((v) => !v)}
            title="Toggle Chat Inbox"
            className="p-1.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] hover:bg-neutral-100 text-[var(--rl-text-strong)] cursor-pointer shrink-0"
          >
            <SidebarSimple size={15} weight={showSidebar ? "fill" : "regular"} />
          </button>
          <div className="size-7 rounded-full bg-[var(--rl-black)] text-white grid place-items-center shrink-0">
            <Robot size={15} weight="fill" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <h3 className="text-xs font-bold text-[var(--rl-text-strong)] truncate">
                {activeThread?.title || "RiskLocker AI Copilot"}
              </h3>
              <Badge variant="default" className="text-[10px] px-1.5 py-0">
                Agentic DB
              </Badge>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={() => createNewThread(contextPinned ? pageContext : undefined)}
            title="New Chat"
            className="inline-flex items-center gap-1 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] px-2 py-1 text-[11px] font-semibold hover:bg-neutral-100 cursor-pointer"
          >
            <Plus size={12} weight="bold" />
            <span className="hidden sm:inline">New</span>
          </button>

          {variant === "sidecar" && (
            <>
              <button
                type="button"
                onClick={() => setDrawerMode(drawerMode === "wide" ? "normal" : "wide")}
                title={drawerMode === "wide" ? "Compact Drawer" : "Expand Wide Drawer"}
                className="p-1.5 rounded-[var(--rl-radius-sm)] hover:bg-neutral-100 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] cursor-pointer"
              >
                {drawerMode === "wide" ? <ArrowsInSimple size={15} /> : <ArrowsOutSimple size={15} />}
              </button>
              <Link
                href={"/copilot" as Route}
                onClick={() => onCloseDrawer?.()}
                title="Open Full-Screen AI Workspace"
                className="p-1.5 rounded-[var(--rl-radius-sm)] hover:bg-neutral-100 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)]"
              >
                <ArrowSquareOut size={15} />
              </Link>
              {onCloseDrawer && (
                <button
                  type="button"
                  onClick={onCloseDrawer}
                  aria-label="Close AI Copilot"
                  className="p-1.5 rounded-[var(--rl-radius-sm)] hover:bg-neutral-100 text-[var(--rl-text-muted)] hover:text-[var(--rl-text-strong)] cursor-pointer"
                >
                  <X size={15} weight="bold" />
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {/* Visible Error Banner */}
      {error && (
        <div className="mx-3 mt-2 rounded-[var(--rl-radius-sm)] border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-800 flex items-center justify-between gap-2 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <WarningCircle size={15} weight="fill" className="text-rose-600 shrink-0" />
            <span className="truncate">{error}</span>
          </div>
          <button
            type="button"
            onClick={clearError}
            className="text-rose-700 hover:text-rose-950 cursor-pointer shrink-0"
          >
            <X size={13} weight="bold" />
          </button>
        </div>
      )}

      {/* Multi-Pane Body */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {showSidebar && (
          <div className={variant === "fullscreen" ? "w-64 shrink-0 h-full" : "w-60 shrink-0 h-full"}>
            <CopilotInboxSidebar
              threads={threads}
              activeThreadId={activeThreadId}
              loading={threadsLoading}
              searchQuery={threadSearch}
              onSearchChange={setThreadSearch}
              onSelectThread={(id) => {
                selectThread(id);
                if (variant === "sidecar" && drawerMode === "normal") {
                  setShowInboxInSidecar(false);
                }
              }}
              onNewChat={() => createNewThread(contextPinned ? pageContext : undefined)}
              onRenameThread={renameThread}
              onTogglePin={togglePinThread}
              onDeleteThread={deleteThread}
            />
          </div>
        )}

        <div className="flex flex-1 min-w-0 flex-col h-full bg-[var(--rl-bg)]/30">
          <CopilotMessageStream
            messages={messages}
            loading={messagesLoading}
            streaming={streaming}
            pageContext={pageContext}
            onSelectStarterPrompt={(prompt) => setExternalDraft(prompt)}
            onOpenArtifact={(art) => setActiveArtifact(art)}
            onFeedback={submitFeedback}
            onRegenerate={(prompt) => sendMessage(prompt)}
          />
          <CopilotComposer
            streaming={streaming}
            quota={quota}
            pageContext={pageContext}
            contextPinned={contextPinned}
            onToggleContextPinned={setContextPinned}
            onSend={(text, opts) => sendMessage(text, opts)}
            onStop={stopStreaming}
            externalDraft={externalDraft}
            onConsumeExternalDraft={() => setExternalDraft("")}
          />
        </div>

        {activeArtifact && (
          <div className={variant === "fullscreen" ? "w-[440px] shrink-0 h-full" : "w-[360px] shrink-0 h-full"}>
            <CopilotArtifactPane
              artifact={activeArtifact}
              onClose={() => setActiveArtifact(null)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
