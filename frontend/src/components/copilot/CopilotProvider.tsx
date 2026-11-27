"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { api, apiRaw } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  CopilotArtifact,
  CopilotDrawerMode,
  CopilotMessage,
  CopilotPageContext,
  CopilotThread,
  CopilotToolStep,
  CopilotUserQuota,
  CopilotVerifiedLink,
} from "./types";

const ACTIVE_THREAD_STORAGE_KEY = "rl_copilot_active_thread_id";
const DRAWER_OPEN_STORAGE_KEY = "rl_copilot_drawer_open";

type CopilotContextValue = {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  drawerMode: CopilotDrawerMode;
  setDrawerMode: (mode: CopilotDrawerMode) => void;
  threads: CopilotThread[];
  threadsLoading: boolean;
  threadSearch: string;
  setThreadSearch: (q: string) => void;
  activeThreadId: string | null;
  activeThread: CopilotThread | null;
  messages: CopilotMessage[];
  messagesLoading: boolean;
  streaming: boolean;
  error: string | null;
  clearError: () => void;
  quota: CopilotUserQuota | null;
  pageContext: CopilotPageContext;
  contextPinned: boolean;
  setContextPinned: (pinned: boolean) => void;
  activeArtifact: CopilotArtifact | null;
  setActiveArtifact: (art: CopilotArtifact | null) => void;
  refreshThreads: (searchOverride?: string) => Promise<void>;
  refreshQuota: () => Promise<void>;
  selectThread: (threadId: string) => Promise<void>;
  createNewThread: (anchor?: Partial<CopilotPageContext>) => Promise<CopilotThread | null>;
  renameThread: (threadId: string, title: string) => Promise<void>;
  togglePinThread: (threadId: string, isPinned: boolean) => Promise<void>;
  deleteThread: (threadId: string) => Promise<void>;
  sendMessage: (
    text: string,
    opts?: { enableWebResearch?: boolean; usePageContext?: boolean }
  ) => Promise<void>;
  stopStreaming: () => void;
  submitFeedback: (messageId: string, feedback: "up" | "down" | null) => Promise<void>;
};

const CopilotContext = createContext<CopilotContextValue | null>(null);

function detectPageContext(pathname: string): CopilotPageContext {
  const ctx: CopilotPageContext = { pathname };
  if (typeof window === "undefined") return ctx;
  const params = new URLSearchParams(window.location.search);

  if (pathname.startsWith("/comparison")) {
    const tid = params.get("tenure_id");
    if (tid) {
      ctx.anchor_type = "tenure";
      ctx.anchor_id = tid;
      ctx.anchor_label = "Current Comparison Car";
    }
  } else if (pathname.startsWith("/sessions/")) {
    const match = pathname.match(/^\/sessions\/(?:sandbox\/)?([^/]+)/);
    if (match && match[1] && match[1] !== "new") {
      ctx.anchor_type = "session";
      ctx.anchor_id = match[1];
      ctx.anchor_label = `Session ${match[1].slice(0, 8)}`;
    }
  } else if (pathname.startsWith("/ledger")) {
    const search = params.get("search");
    if (search) {
      ctx.anchor_type = "vehicle";
      ctx.anchor_id = search;
      ctx.anchor_label = `Ledger Filter: ${search}`;
    }
  } else if (pathname.startsWith("/client-records")) {
    const search = params.get("search");
    if (search) {
      ctx.anchor_type = "client";
      ctx.anchor_id = search;
      ctx.anchor_label = `Client: ${search}`;
    }
  }
  return ctx;
}

export function CopilotProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || "/";
  const { user } = useAuth();
  const isStaffOrAdmin = !!user && ["super_admin", "admin", "dev", "staff"].includes(user.role);

  const [isOpen, setIsOpenState] = useState(false);
  const [drawerMode, setDrawerMode] = useState<CopilotDrawerMode>("normal");
  const [threads, setThreads] = useState<CopilotThread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const [threadSearch, setThreadSearch] = useState("");
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quota, setQuota] = useState<CopilotUserQuota | null>(null);
  const [pageContext, setPageContext] = useState<CopilotPageContext>({ pathname });
  const [contextPinned, setContextPinned] = useState(true);
  const [activeArtifact, setActiveArtifact] = useState<CopilotArtifact | null>(null);

  const abortRef = useRef<AbortController | null>(null);

  const setIsOpen = useCallback((open: boolean) => {
    setIsOpenState(open);
    try {
      sessionStorage.setItem(DRAWER_OPEN_STORAGE_KEY, open ? "1" : "0");
    } catch {}
  }, []);

  // Sync active page context on route change
  useEffect(() => {
    const nextCtx = detectPageContext(pathname);
    setPageContext(nextCtx);
    if (nextCtx.anchor_id) {
      setContextPinned(true);
    }
  }, [pathname]);

  // Restore open/thread state across client navigations
  useEffect(() => {
    try {
      const wasOpen = sessionStorage.getItem(DRAWER_OPEN_STORAGE_KEY) === "1";
      if (wasOpen && pathname !== "/copilot") {
        setIsOpenState(true);
      }
      const savedTid = sessionStorage.getItem(ACTIVE_THREAD_STORAGE_KEY);
      if (savedTid) {
        setActiveThreadId(savedTid);
      }
    } catch {}
  }, [pathname]);

  // Global Ctrl+K / Cmd+K shortcut
  useEffect(() => {
    if (!isStaffOrAdmin) return;
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (pathname === "/copilot") return;
        setIsOpenState((prev) => {
          const next = !prev;
          try {
            sessionStorage.setItem(DRAWER_OPEN_STORAGE_KEY, next ? "1" : "0");
          } catch {}
          return next;
        });
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isStaffOrAdmin, pathname]);

  const refreshQuota = useCallback(async () => {
    if (!isStaffOrAdmin) return;
    try {
      const q = await api<CopilotUserQuota>("/copilot/quota");
      setQuota(q);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Copilot quota.");
    }
  }, [isStaffOrAdmin]);

  const refreshThreads = useCallback(
    async (searchOverride?: string) => {
      if (!isStaffOrAdmin) return;
      setThreadsLoading(true);
      try {
        const q = (searchOverride ?? threadSearch).trim();
        const qs = q ? `?search=${encodeURIComponent(q)}&limit=50` : "?limit=50";
        const res = await api<{ threads: CopilotThread[] }>(`/copilot/threads${qs}`);
        setThreads(res.threads || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load Copilot threads.");
      } finally {
        setThreadsLoading(false);
      }
    },
    [isStaffOrAdmin, threadSearch]
  );

  const selectThread = useCallback(
    async (threadId: string) => {
      if (!isStaffOrAdmin) return;
      setActiveThreadId(threadId);
      setActiveArtifact(null);
      setError(null);
      try {
        sessionStorage.setItem(ACTIVE_THREAD_STORAGE_KEY, threadId);
      } catch {}
      setMessagesLoading(true);
      try {
        const res = await api<{
          thread: CopilotThread;
          messages: CopilotMessage[];
          artifacts: CopilotArtifact[];
        }>(`/copilot/threads/${threadId}`);
        setMessages(res.messages || []);
        setThreads((prev) => {
          const exists = prev.some((t) => t.id === res.thread.id);
          return exists ? prev.map((t) => (t.id === res.thread.id ? res.thread : t)) : [res.thread, ...prev];
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load conversation.");
        setMessages([]);
      } finally {
        setMessagesLoading(false);
      }
    },
    [isStaffOrAdmin]
  );

  // Initial load when Copilot becomes visible (sidecar opened or on /copilot)
  useEffect(() => {
    if (!isStaffOrAdmin) return;
    if (!isOpen && pathname !== "/copilot") return;
    refreshQuota();
    refreshThreads();
  }, [isStaffOrAdmin, isOpen, pathname, refreshQuota, refreshThreads]);

  useEffect(() => {
    if (!isStaffOrAdmin) return;
    if (!isOpen && pathname !== "/copilot") return;
    if (activeThreadId && messages.length === 0 && !messagesLoading && !streaming) {
      selectThread(activeThreadId);
    }
  }, [isStaffOrAdmin, isOpen, pathname, activeThreadId, messages.length, messagesLoading, streaming, selectThread]);

  const createNewThread = useCallback(
    async (anchor?: Partial<CopilotPageContext>): Promise<CopilotThread | null> => {
      if (!isStaffOrAdmin) return null;
      setError(null);
      try {
        const payload = anchor?.anchor_id
          ? {
              anchor_type: anchor.anchor_type || null,
              anchor_id: anchor.anchor_id || null,
              anchor_label: anchor.anchor_label || null,
            }
          : {};
        const res = await api<{ thread: CopilotThread }>("/copilot/threads", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        setThreads((prev) => [res.thread, ...prev]);
        setActiveThreadId(res.thread.id);
        setMessages([]);
        setActiveArtifact(null);
        try {
          sessionStorage.setItem(ACTIVE_THREAD_STORAGE_KEY, res.thread.id);
        } catch {}
        return res.thread;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not create chat session.");
        return null;
      }
    },
    [isStaffOrAdmin]
  );

  const renameThread = useCallback(async (threadId: string, title: string) => {
    setError(null);
    try {
      const res = await api<{ thread: CopilotThread }>(`/copilot/threads/${threadId}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      });
      setThreads((prev) => prev.map((t) => (t.id === threadId ? res.thread : t)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to rename thread.");
    }
  }, []);

  const togglePinThread = useCallback(async (threadId: string, isPinned: boolean) => {
    setError(null);
    try {
      const res = await api<{ thread: CopilotThread }>(`/copilot/threads/${threadId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_pinned: isPinned }),
      });
      setThreads((prev) => {
        const updated = prev.map((t) => (t.id === threadId ? res.thread : t));
        return [...updated].sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned));
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update pin status.");
    }
  }, []);

  const deleteThread = useCallback(
    async (threadId: string) => {
      setError(null);
      try {
        await api(`/copilot/threads/${threadId}`, { method: "DELETE" });
        setThreads((prev) => prev.filter((t) => t.id !== threadId));
        if (activeThreadId === threadId) {
          setActiveThreadId(null);
          setMessages([]);
          setActiveArtifact(null);
          try {
            sessionStorage.removeItem(ACTIVE_THREAD_STORAGE_KEY);
          } catch {}
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete chat session.");
      }
    },
    [activeThreadId]
  );

  const stopStreaming = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStreaming(false);
    setMessages((prev) =>
      prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false, content_markdown: m.content_markdown || "_Stopped._" } : m))
    );
  }, []);

  const sendMessage = useCallback(
    async (text: string, opts?: { enableWebResearch?: boolean; usePageContext?: boolean }) => {
      const cleaned = text.trim();
      if (!cleaned || streaming || !isStaffOrAdmin) return;
      setError(null);

      let targetThreadId = activeThreadId;
      if (!targetThreadId) {
        const created = await createNewThread(
          opts?.usePageContext !== false && contextPinned ? pageContext : undefined
        );
        if (!created) return;
        targetThreadId = created.id;
      }

      const tempUserId = `u-${Date.now()}`;
      const tempAssistantId = `a-${Date.now()}`;
      const userMsg: CopilotMessage = {
        id: tempUserId,
        thread_id: targetThreadId,
        role: "user",
        content_markdown: cleaned,
        tool_trace: [],
        verified_links: [],
        action_cards: [],
        artifacts: [],
        created_at: new Date().toISOString(),
      };
      const assistantPlaceholder: CopilotMessage = {
        id: tempAssistantId,
        thread_id: targetThreadId,
        role: "assistant",
        content_markdown: "",
        tool_trace: [],
        verified_links: [],
        action_cards: [],
        artifacts: [],
        isStreaming: true,
        created_at: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg, assistantPlaceholder]);
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await apiRaw(`/copilot/threads/${targetThreadId}/stream`, {
          method: "POST",
          signal: controller.signal,
          body: JSON.stringify({
            message: cleaned,
            enable_web_research: !!opts?.enableWebResearch,
            page_context: opts?.usePageContext !== false && contextPinned ? pageContext : null,
          }),
        });

        if (!res.ok) {
          let errMsg = `Request failed (${res.status})`;
          try {
            const j = await res.json();
            errMsg = j?.error?.message || errMsg;
          } catch {}
          throw new Error(errMsg);
        }
        if (!res.body) {
          throw new Error("Streaming response body was empty.");
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const frames = buffer.split("\n\n");
          buffer = frames.pop() || "";

          for (const frame of frames) {
            const line = frame
              .split("\n")
              .find((l) => l.startsWith("data: "));
            if (!line) continue;
            let evt: any;
            try {
              evt = JSON.parse(line.slice(6));
            } catch {
              continue;
            }

            if (evt.type === "thread" && evt.thread) {
              setThreads((prev) => prev.map((t) => (t.id === evt.thread.id ? evt.thread : t)));
            } else if (evt.type === "step") {
              const step: CopilotToolStep = {
                step_id: evt.step_id,
                status: evt.status,
                tool: evt.tool,
                label: evt.label,
                sql: evt.sql,
                row_count: evt.row_count,
                elapsed_ms: evt.elapsed_ms,
              };
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== tempAssistantId) return m;
                  const exists = m.tool_trace.some((s) => s.step_id === step.step_id);
                  const nextTrace = exists
                    ? m.tool_trace.map((s) => (s.step_id === step.step_id ? step : s))
                    : [...m.tool_trace, step];
                  return { ...m, tool_trace: nextTrace };
                })
              );
            } else if (evt.type === "artifact" && evt.artifact) {
              const art: CopilotArtifact = evt.artifact;
              setMessages((prev) =>
                prev.map((m) => (m.id === tempAssistantId ? { ...m, artifacts: [...m.artifacts, art] } : m))
              );
            } else if (evt.type === "links" && Array.isArray(evt.links)) {
              const links: CopilotVerifiedLink[] = evt.links;
              setMessages((prev) =>
                prev.map((m) => (m.id === tempAssistantId ? { ...m, verified_links: links } : m))
              );
            } else if (evt.type === "actions" && Array.isArray(evt.actions)) {
              setMessages((prev) =>
                prev.map((m) => (m.id === tempAssistantId ? { ...m, action_cards: evt.actions } : m))
              );
            } else if (evt.type === "delta" && typeof evt.text === "string") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === tempAssistantId
                    ? { ...m, content_markdown: `${m.content_markdown}${evt.text}` }
                    : m
                )
              );
            } else if (evt.type === "done") {
              if (evt.thread) {
                setThreads((prev) => {
                  const others = prev.filter((t) => t.id !== evt.thread.id);
                  return [evt.thread, ...others].sort((a, b) => Number(b.is_pinned) - Number(a.is_pinned));
                });
              }
              if (evt.message) {
                setMessages((prev) =>
                  prev.map((m) => (m.id === tempAssistantId ? { ...evt.message, isStreaming: false } : m))
                );
              }
              if (evt.quota) {
                setQuota(evt.quota);
              }
            } else if (evt.type === "error") {
              setError(evt.message || "Copilot request failed.");
              if (evt.quota) setQuota(evt.quota);
              setMessages((prev) => prev.filter((m) => m.id !== tempAssistantId));
            }
          }
        }
      } catch (err: any) {
        if (err?.name !== "AbortError") {
          setError(err instanceof Error ? err.message : "Failed to stream Copilot response.");
          setMessages((prev) =>
            prev.map((m) =>
              m.id === tempAssistantId
                ? {
                    ...m,
                    isStreaming: false,
                    content_markdown: m.content_markdown || "Could not complete request.",
                  }
                : m
            )
          );
        }
      } finally {
        abortRef.current = null;
        setStreaming(false);
        setMessages((prev) => prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)));
      }
    },
    [activeThreadId, contextPinned, createNewThread, isStaffOrAdmin, pageContext, streaming]
  );

  const submitFeedback = useCallback(async (messageId: string, feedback: "up" | "down" | null) => {
    setError(null);
    try {
      await api(`/copilot/messages/${messageId}/feedback`, {
        method: "POST",
        body: JSON.stringify({ feedback }),
      });
      setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, feedback } : m)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save feedback.");
    }
  }, []);

  const activeThread = useMemo(
    () => threads.find((t) => t.id === activeThreadId) || null,
    [threads, activeThreadId]
  );

  const value: CopilotContextValue = {
    isOpen,
    setIsOpen,
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
    clearError: () => setError(null),
    quota,
    pageContext,
    contextPinned,
    setContextPinned,
    activeArtifact,
    setActiveArtifact,
    refreshThreads,
    refreshQuota,
    selectThread,
    createNewThread,
    renameThread,
    togglePinThread,
    deleteThread,
    sendMessage,
    stopStreaming,
    submitFeedback,
  };

  return <CopilotContext.Provider value={value}>{children}</CopilotContext.Provider>;
}

export function useCopilot() {
  const ctx = useContext(CopilotContext);
  if (!ctx) {
    throw new Error("useCopilot must be used inside CopilotProvider");
  }
  return ctx;
}
