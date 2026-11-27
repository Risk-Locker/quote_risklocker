"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { api, apiRaw } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type {
  CopilotAdminUser,
  CopilotArtifact,
  CopilotDrawerMode,
  CopilotMessage,
  CopilotPageContext,
  CopilotQueueStatus,
  CopilotThread,
  CopilotToolStep,
  CopilotUserQuota,
  CopilotVerifiedLink,
} from "./types";

const DRAWER_OPEN_STORAGE_KEY = "rl_copilot_drawer_open";
const DRAWER_WIDTH_STORAGE_KEY = "rl_copilot_drawer_width";
const DRAWER_MODE_STORAGE_KEY = "rl_copilot_drawer_mode";

function activeThreadKey(userId?: string | null): string {
  return userId ? `rl_copilot_active_thread_${userId}` : "rl_copilot_active_thread_anon";
}

type CopilotContextValue = {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  drawerMode: CopilotDrawerMode;
  setDrawerMode: (mode: CopilotDrawerMode) => void;
  drawerWidth: number;
  setDrawerWidth: (width: number) => void;
  dockedFromNavigation: boolean;
  dockAfterNavigation: () => void;
  restoreFromDock: () => void;
  threads: CopilotThread[];
  threadsLoading: boolean;
  threadSearch: string;
  setThreadSearch: (q: string) => void;
  activeThreadId: string | null;
  activeThread: CopilotThread | null;
  messages: CopilotMessage[];
  messagesLoading: boolean;
  streaming: boolean;
  queueStatus: CopilotQueueStatus | null;
  error: string | null;
  clearError: () => void;
  quota: CopilotUserQuota | null;
  pageContext: CopilotPageContext;
  contextPinned: boolean;
  setContextPinned: (pinned: boolean) => void;
  activeArtifact: CopilotArtifact | null;
  setActiveArtifact: (art: CopilotArtifact | null) => void;
  // Admin oversight
  isAdminUser: boolean;
  adminUsers: CopilotAdminUser[];
  viewingUserId: string | null;
  setViewingUserId: (uid: string | null) => void;
  isReadOnlyOversight: boolean;
  viewingUser: CopilotAdminUser | null;
  refreshAdminUsers: () => Promise<void>;
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
  const isAdminUser = !!user && ["super_admin", "admin", "dev"].includes(user.role);

  const [isOpen, setIsOpenState] = useState(false);
  const [drawerMode, setDrawerModeState] = useState<CopilotDrawerMode>("compact");
  const [drawerWidth, setDrawerWidthState] = useState<number>(520);
  const [dockedFromNavigation, setDockedFromNavigation] = useState(false);

  const [threads, setThreads] = useState<CopilotThread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);
  const [threadSearch, setThreadSearch] = useState("");
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [messagesLoading, setMessagesLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [queueStatus, setQueueStatus] = useState<CopilotQueueStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [quota, setQuota] = useState<CopilotUserQuota | null>(null);
  const [pageContext, setPageContext] = useState<CopilotPageContext>({ pathname });
  const [contextPinned, setContextPinned] = useState(true);
  const [activeArtifact, setActiveArtifact] = useState<CopilotArtifact | null>(null);

  // Admin oversight state
  const [adminUsers, setAdminUsers] = useState<CopilotAdminUser[]>([]);
  const [viewingUserId, setViewingUserIdState] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const prevUserIdRef = useRef<string | null>(null);
  const loadedThreadIdRef = useRef<string | null>(null);
  const loadSeqRef = useRef<number>(0);

  const setIsOpen = useCallback((open: boolean) => {
    setIsOpenState(open);
    if (open) setDockedFromNavigation(false);
    try {
      sessionStorage.setItem(DRAWER_OPEN_STORAGE_KEY, open ? "1" : "0");
    } catch {}
  }, []);

  const setDrawerMode = useCallback((mode: CopilotDrawerMode) => {
    setDrawerModeState(mode);
    try {
      localStorage.setItem(DRAWER_MODE_STORAGE_KEY, mode);
    } catch {}
  }, []);

  const setDrawerWidth = useCallback((w: number) => {
    const clamped = Math.max(420, Math.min(1400, Math.round(w)));
    setDrawerWidthState(clamped);
    try {
      localStorage.setItem(DRAWER_WIDTH_STORAGE_KEY, String(clamped));
    } catch {}
  }, []);

  const dockAfterNavigation = useCallback(() => {
    if (pathname === "/copilot") return;
    setIsOpenState(false);
    setDockedFromNavigation(true);
    try {
      sessionStorage.setItem(DRAWER_OPEN_STORAGE_KEY, "0");
    } catch {}
  }, [pathname]);

  const restoreFromDock = useCallback(() => {
    setDockedFromNavigation(false);
    setIsOpen(true);
  }, [setIsOpen]);

  // Reset per-user state cleanly whenever logged-in user changes or logs out
  useEffect(() => {
    const uid = user?.id || null;
    if (prevUserIdRef.current !== uid) {
      prevUserIdRef.current = uid;
      loadedThreadIdRef.current = null;
      loadSeqRef.current += 1;
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
      setStreaming(false);
      setQueueStatus(null);
      setThreads([]);
      setMessages([]);
      setActiveArtifact(null);
      setViewingUserIdState(null);
      setAdminUsers([]);
      setError(null);
      try {
        const savedTid = uid ? sessionStorage.getItem(activeThreadKey(uid)) : null;
        setActiveThreadId(savedTid || null);
      } catch {
        setActiveThreadId(null);
      }
    }
  }, [user?.id]);

  // Restore drawer preferences on mount
  useEffect(() => {
    try {
      const savedMode = localStorage.getItem(DRAWER_MODE_STORAGE_KEY);
      if (savedMode === "compact" || savedMode === "wide" || savedMode === "modal") {
        setDrawerModeState(savedMode);
      }
      const savedWidth = Number(localStorage.getItem(DRAWER_WIDTH_STORAGE_KEY) || 0);
      if (savedWidth >= 420 && savedWidth <= 1400) {
        setDrawerWidthState(savedWidth);
      }
      const wasOpen = sessionStorage.getItem(DRAWER_OPEN_STORAGE_KEY) === "1";
      if (wasOpen && pathname !== "/copilot") {
        setIsOpenState(true);
      }
    } catch {}
  }, [pathname]);

  // Sync active page context on route change
  useEffect(() => {
    const nextCtx = detectPageContext(pathname);
    setPageContext(nextCtx);
    if (nextCtx.anchor_id) {
      setContextPinned(true);
    }
  }, [pathname]);

  // Global Ctrl+K / Cmd+K shortcut + Escape to close modal
  useEffect(() => {
    if (!isStaffOrAdmin) return;
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        if (pathname === "/copilot") return;
        setIsOpenState((prev) => {
          const next = !prev;
          if (next) setDockedFromNavigation(false);
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

  const isReadOnlyOversight = !!viewingUserId && !!user?.id && viewingUserId !== user.id;

  const viewingUser = useMemo(
    () => adminUsers.find((u) => u.id === viewingUserId) || null,
    [adminUsers, viewingUserId]
  );

  const refreshQuota = useCallback(async () => {
    if (!isStaffOrAdmin) return;
    try {
      const q = await api<CopilotUserQuota>("/copilot/quota");
      setQuota(q);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load Copilot quota.");
    }
  }, [isStaffOrAdmin]);

  const refreshAdminUsers = useCallback(async () => {
    if (!isAdminUser) return;
    try {
      const res = await api<{ users: CopilotAdminUser[] }>("/copilot/admin/users");
      setAdminUsers(res.users || []);
    } catch {
      // Non-fatal if user lacks access
    }
  }, [isAdminUser]);

  const refreshThreads = useCallback(
    async (searchOverride?: string, targetUidOverride?: string | null) => {
      if (!isStaffOrAdmin) return;
      setThreadsLoading(true);
      try {
        const q = (searchOverride ?? threadSearch).trim();
        const params = new URLSearchParams();
        params.set("limit", "60");
        if (q) params.set("search", q);
        const effUid = targetUidOverride !== undefined ? targetUidOverride : viewingUserId;
        if (isAdminUser && effUid && effUid !== user?.id) {
          params.set("user_id", effUid);
        }
        const res = await api<{ threads: CopilotThread[] }>(`/copilot/threads?${params.toString()}`);
        setThreads(res.threads || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load Copilot threads.");
      } finally {
        setThreadsLoading(false);
      }
    },
    [isStaffOrAdmin, isAdminUser, threadSearch, viewingUserId, user?.id]
  );

  const setViewingUserId = useCallback(
    (uid: string | null) => {
      const normalized = uid && uid !== user?.id ? uid : null;
      loadedThreadIdRef.current = null;
      loadSeqRef.current += 1;
      setViewingUserIdState(normalized);
      setActiveThreadId(null);
      setMessages([]);
      setActiveArtifact(null);
      setError(null);
    },
    [user?.id]
  );

  const selectThread = useCallback(
    async (threadId: string) => {
      if (!isStaffOrAdmin) return;
      const seq = ++loadSeqRef.current;
      loadedThreadIdRef.current = threadId;
      setActiveThreadId(threadId);
      setActiveArtifact(null);
      setError(null);
      if (!isReadOnlyOversight) {
        try {
          sessionStorage.setItem(activeThreadKey(user?.id), threadId);
        } catch {}
      }
      setMessagesLoading(true);
      try {
        const res = await api<{
          thread: CopilotThread;
          messages: CopilotMessage[];
          artifacts: CopilotArtifact[];
        }>(`/copilot/threads/${threadId}`);
        if (seq !== loadSeqRef.current) return;
        setMessages(res.messages || []);
        setThreads((prev) => {
          const exists = prev.some((t) => t.id === res.thread.id);
          return exists ? prev.map((t) => (t.id === res.thread.id ? res.thread : t)) : [res.thread, ...prev];
        });
      } catch (err) {
        if (seq !== loadSeqRef.current) return;
        const msg = err instanceof Error ? err.message : "Failed to load conversation.";
        setError(msg);
        setMessages([]);
        if (/404|403|not found|forbidden/i.test(msg)) {
          setActiveThreadId(null);
          loadedThreadIdRef.current = null;
          if (!isReadOnlyOversight) {
            try {
              sessionStorage.removeItem(activeThreadKey(user?.id));
            } catch {}
          }
        }
      } finally {
        if (seq === loadSeqRef.current) {
          setMessagesLoading(false);
        }
      }
    },
    [isStaffOrAdmin, isReadOnlyOversight, user?.id]
  );

  // Load quota and admin user directory when Copilot becomes visible
  useEffect(() => {
    if (!isStaffOrAdmin) return;
    if (!isOpen && pathname !== "/copilot") return;
    void refreshQuota();
    if (isAdminUser) {
      void refreshAdminUsers();
    }
  }, [isStaffOrAdmin, isAdminUser, isOpen, pathname, refreshQuota, refreshAdminUsers]);

  // Load threads list when Copilot opens, viewed account changes, or search updates (debounced)
  useEffect(() => {
    if (!isStaffOrAdmin) return;
    if (!isOpen && pathname !== "/copilot") return;
    const delay = threadSearch.trim() ? 250 : 0;
    const timer = window.setTimeout(() => {
      void refreshThreads();
    }, delay);
    return () => window.clearTimeout(timer);
  }, [isStaffOrAdmin, isOpen, pathname, threadSearch, viewingUserId, refreshThreads]);

  // One-shot thread hydration (never re-fetches on empty message arrays)
  useEffect(() => {
    if (!isStaffOrAdmin) return;
    if (!isOpen && pathname !== "/copilot") return;
    if (!activeThreadId || streaming) return;
    if (loadedThreadIdRef.current === activeThreadId) return;
    void selectThread(activeThreadId);
  }, [isStaffOrAdmin, isOpen, pathname, activeThreadId, streaming, selectThread]);

  const createNewThread = useCallback(
    async (anchor?: Partial<CopilotPageContext>): Promise<CopilotThread | null> => {
      if (!isStaffOrAdmin) return null;
      if (isReadOnlyOversight) {
        setViewingUserIdState(null);
      }
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
        loadSeqRef.current += 1;
        loadedThreadIdRef.current = res.thread.id;
        setActiveThreadId(res.thread.id);
        setMessages([]);
        setActiveArtifact(null);
        try {
          sessionStorage.setItem(activeThreadKey(user?.id), res.thread.id);
        } catch {}
        return res.thread;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not create chat session.");
        return null;
      }
    },
    [isStaffOrAdmin, isReadOnlyOversight, user?.id]
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
          loadedThreadIdRef.current = null;
          loadSeqRef.current += 1;
          setActiveThreadId(null);
          setMessages([]);
          setActiveArtifact(null);
          try {
            sessionStorage.removeItem(activeThreadKey(user?.id));
          } catch {}
        }
        if (isAdminUser) {
          void refreshAdminUsers();
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to delete chat session.");
      }
    },
    [activeThreadId, user?.id, isAdminUser, refreshAdminUsers]
  );

  const stopStreaming = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStreaming(false);
    setQueueStatus(null);
    setMessages((prev) =>
      prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false, content_markdown: m.content_markdown || "_Stopped._" } : m))
    );
  }, []);

  const sendMessage = useCallback(
    async (text: string, opts?: { enableWebResearch?: boolean; usePageContext?: boolean }) => {
      const cleaned = text.trim();
      if (!cleaned || streaming || !isStaffOrAdmin || isReadOnlyOversight) return;
      setError(null);
      setQueueStatus(null);

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

            if (evt.type === "queue_status") {
              setQueueStatus({
                reason: evt.reason,
                position: evt.position,
                active_users: evt.active_users,
                inflight_turns: evt.inflight_turns,
                wait_seconds: evt.wait_seconds,
                estimated_tokens: evt.estimated_tokens,
              });
            } else if (evt.type === "thread" && evt.thread) {
              setThreads((prev) => prev.map((t) => (t.id === evt.thread.id ? evt.thread : t)));
            } else if (evt.type === "step") {
              setQueueStatus(null);
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
              setQueueStatus(null);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === tempAssistantId
                    ? { ...m, content_markdown: `${m.content_markdown}${evt.text}` }
                    : m
                )
              );
            } else if (evt.type === "done") {
              setQueueStatus(null);
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
              setQueueStatus(null);
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
        setQueueStatus(null);
        setMessages((prev) => prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)));
      }
    },
    [activeThreadId, contextPinned, createNewThread, isStaffOrAdmin, isReadOnlyOversight, pageContext, streaming]
  );

  const submitFeedback = useCallback(async (messageId: string, feedback: "up" | "down" | null) => {
    if (isReadOnlyOversight) return;
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
  }, [isReadOnlyOversight]);

  const activeThread = useMemo(
    () => threads.find((t) => t.id === activeThreadId) || null,
    [threads, activeThreadId]
  );

  const value: CopilotContextValue = {
    isOpen,
    setIsOpen,
    drawerMode,
    setDrawerMode,
    drawerWidth,
    setDrawerWidth,
    dockedFromNavigation,
    dockAfterNavigation,
    restoreFromDock,
    threads,
    threadsLoading,
    threadSearch,
    setThreadSearch,
    activeThreadId,
    activeThread,
    messages,
    messagesLoading,
    streaming,
    queueStatus,
    error,
    clearError: () => setError(null),
    quota,
    pageContext,
    contextPinned,
    setContextPinned,
    activeArtifact,
    setActiveArtifact,
    isAdminUser,
    adminUsers,
    viewingUserId,
    setViewingUserId,
    isReadOnlyOversight,
    viewingUser,
    refreshAdminUsers,
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
