"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API_BASE, CLIENT_TAB_ID, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export type RealtimeScope = "ledger" | "comparison" | "workspace" | "sessions" | "clients" | "upload_runs";

export interface RealtimeEditor {
  scope: RealtimeScope;
  resource_id: string;
  user_id: string;
  user_email: string;
  user_name: string;
  field?: string | null;
  updated_at: string;
}

export interface RealtimeUpdateEvent {
  scope: RealtimeScope;
  resource_id: string;
  actor_id?: string | null;
  actor_email?: string | null;
  actor_name?: string | null;
  origin_tab_id?: string | null;
  summary?: string | null;
  version: number;
  timestamp: string;
}

interface RealtimePresenceEvent {
  scope: RealtimeScope;
  resource_id: string;
  active_editors: RealtimeEditor[];
  timestamp: string;
}

type Listener = {
  onConnected: (payload: { user_id?: string; version?: number }) => void;
  onPresence: (payload: RealtimePresenceEvent) => void;
  onUpdated: (payload: RealtimeUpdateEvent) => void;
  onConnectionChange: (connected: boolean) => void;
};

// Shared singleton EventSource + BroadcastChannel fan-out across 10+ browser tabs.
class RealtimeClientSingleton {
  private es: EventSource | null = null;
  private bc: BroadcastChannel | null = null;
  private seenKeys = new Set<string>();
  private seenOrder: string[] = [];
  private listeners = new Set<Listener>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private backoffMs = 1000;
  private isConnected = false;

  subscribe(listener: Listener): () => void {
    this.listeners.add(listener);
    listener.onConnectionChange(this.isConnected);
    this.ensureBroadcastChannel();
    this.ensureConnected();
    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0) {
        this.teardown();
      }
    };
  }

  private rememberEvent(payload: RealtimeUpdateEvent): boolean {
    const key = `${payload.version}:${payload.scope}:${payload.resource_id}:${payload.timestamp}`;
    if (this.seenKeys.has(key)) return false;
    this.seenKeys.add(key);
    this.seenOrder.push(key);
    if (this.seenOrder.length > 128) {
      const oldest = this.seenOrder.shift();
      if (oldest) this.seenKeys.delete(oldest);
    }
    return true;
  }

  private ensureBroadcastChannel() {
    if (typeof BroadcastChannel === "undefined" || this.bc) return;
    try {
      const bc = new BroadcastChannel("risklocker-realtime-v1");
      bc.onmessage = (ev: MessageEvent) => {
        const msg = ev?.data;
        if (!msg || msg.sourceTabId === CLIENT_TAB_ID) return;
        if (msg.type === "updated" && msg.payload) {
          const data = msg.payload as RealtimeUpdateEvent;
          if (this.rememberEvent(data)) {
            this.listeners.forEach((l) => l.onUpdated(data));
          }
        }
      };
      this.bc = bc;
    } catch {
      this.bc = null;
    }
  }

  private setConnected(next: boolean) {
    if (this.isConnected === next) return;
    this.isConnected = next;
    this.listeners.forEach((l) => l.onConnectionChange(next));
  }

  private ensureConnected() {
    if (typeof window === "undefined" || this.es) return;
    try {
      const es = new EventSource(`${API_BASE}/realtime/events`, { withCredentials: true });
      this.es = es;

      es.addEventListener("connected", (ev: MessageEvent) => {
        this.backoffMs = 1000;
        this.setConnected(true);
        try {
          const data = JSON.parse(ev.data || "{}");
          this.listeners.forEach((l) => l.onConnected(data));
        } catch {
          // Ignore malformed frame
        }
      });

      es.addEventListener("presence", (ev: MessageEvent) => {
        try {
          const data = JSON.parse(ev.data || "{}") as RealtimePresenceEvent;
          this.listeners.forEach((l) => l.onPresence(data));
        } catch {
          // Ignore malformed frame
        }
      });

      es.addEventListener("updated", (ev: MessageEvent) => {
        try {
          const data = JSON.parse(ev.data || "{}") as RealtimeUpdateEvent;
          if (!this.rememberEvent(data)) return;
          this.listeners.forEach((l) => l.onUpdated(data));
          try {
            this.bc?.postMessage({ sourceTabId: CLIENT_TAB_ID, type: "updated", payload: data });
          } catch {
            // BroadcastChannel optional
          }
        } catch {
          // Ignore malformed frame
        }
      });

      es.onerror = () => {
        this.setConnected(false);
        this.es?.close();
        this.es = null;
        if (this.listeners.size > 0 && !this.reconnectTimer) {
          const wait = this.backoffMs;
          this.backoffMs = Math.min(this.backoffMs * 2, 10000);
          this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.ensureConnected();
          }, wait);
        }
      };
    } catch {
      this.setConnected(false);
    }
  }

  private teardown() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.es) {
      this.es.close();
      this.es = null;
    }
    if (this.bc) {
      try {
        this.bc.close();
      } catch {
        // Ignore close error
      }
      this.bc = null;
    }
    this.setConnected(false);
  }
}

const singleton = new RealtimeClientSingleton();

export interface UseRealtimeSyncOptions {
  scope: RealtimeScope;
  resourceId?: string;
  hasUnsavedChanges?: boolean;
  onRemoteUpdate?: (event: RealtimeUpdateEvent) => void | Promise<void>;
  enabled?: boolean;
}

export function useRealtimeSync({
  scope,
  resourceId = "all",
  hasUnsavedChanges = false,
  onRemoteUpdate,
  enabled = true,
}: UseRealtimeSyncOptions) {
  const { user } = useAuth();
  const [connected, setConnected] = useState(false);
  const [activeEditors, setActiveEditors] = useState<RealtimeEditor[]>([]);
  const [pendingUpdate, setPendingUpdate] = useState<RealtimeUpdateEvent | null>(null);

  const hasUnsavedRef = useRef(hasUnsavedChanges);
  hasUnsavedRef.current = hasUnsavedChanges;

  const onRemoteUpdateRef = useRef(onRemoteUpdate);
  onRemoteUpdateRef.current = onRemoteUpdate;

  const currentUserIdRef = useRef<string | undefined>(user?.id);
  currentUserIdRef.current = user?.id;

  const lastVersionRef = useRef<number>(0);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastPresenceSentAtRef = useRef<number>(0);
  const lastPresenceFieldRef = useRef<string | null>(null);

  const matchesTarget = useCallback(
    (eventScope: string, eventResourceId: string) => {
      if (eventScope !== scope) return false;
      if (resourceId === "all" || eventResourceId === "all") return true;
      return eventResourceId === resourceId;
    },
    [scope, resourceId],
  );

  // Fetch initial presence snapshot & fallback poll when SSE is disconnected.
  const fetchPresenceSnapshot = useCallback(async () => {
    if (!enabled) return;
    try {
      const res = await api<{
        version: number;
        active_editors: RealtimeEditor[];
      }>(`/realtime/presence?scope=${encodeURIComponent(scope)}&resource_id=${encodeURIComponent(resourceId)}`);
      if (Array.isArray(res?.active_editors)) {
        setActiveEditors(res.active_editors);
      }
      if (typeof res?.version === "number" && res.version > lastVersionRef.current) {
        const prev = lastVersionRef.current;
        lastVersionRef.current = res.version;
        // If we missed updates while disconnected, trigger safe refresh.
        if (prev > 0 && !connected) {
          if (hasUnsavedRef.current) {
            setPendingUpdate({
              scope,
              resource_id: resourceId,
              summary: "Remote changes detected",
              version: res.version,
              timestamp: new Date().toISOString(),
            });
          } else {
            void onRemoteUpdateRef.current?.({
              scope,
              resource_id: resourceId,
              summary: "Synced missed update",
              version: res.version,
              timestamp: new Date().toISOString(),
            });
          }
        }
      }
    } catch {
      // Non-blocking background sync
    }
  }, [enabled, scope, resourceId, connected]);

  useEffect(() => {
    if (!enabled) return;
    void fetchPresenceSnapshot();

    const unsubscribe = singleton.subscribe({
      onConnectionChange: (isConn) => setConnected(isConn),
      onConnected: (payload) => {
        if (payload?.user_id && !currentUserIdRef.current) {
          currentUserIdRef.current = payload.user_id;
        }
        if (typeof payload?.version === "number") {
          lastVersionRef.current = Math.max(lastVersionRef.current, payload.version);
        }
        void fetchPresenceSnapshot();
      },
      onPresence: (payload) => {
        if (!matchesTarget(payload.scope, payload.resource_id)) return;
        setActiveEditors(Array.isArray(payload.active_editors) ? payload.active_editors : []);
      },
      onUpdated: (payload) => {
        if (typeof payload.version === "number") {
          lastVersionRef.current = Math.max(lastVersionRef.current, payload.version);
        }
        if (!matchesTarget(payload.scope, payload.resource_id)) return;
        if (payload.origin_tab_id && payload.origin_tab_id === CLIENT_TAB_ID) {
          return;
        }
        if (hasUnsavedRef.current) {
          setPendingUpdate(payload);
          return;
        }
        if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = setTimeout(() => {
          refreshTimerRef.current = null;
          setPendingUpdate(null);
          void onRemoteUpdateRef.current?.(payload);
        }, 60);
      },
    });

    const fallbackInterval = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        void fetchPresenceSnapshot();
      }
    }, 10000);

    return () => {
      unsubscribe();
      clearInterval(fallbackInterval);
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [enabled, matchesTarget, fetchPresenceSnapshot]);

  const reportEditing = useCallback(
    async (field?: string | null) => {
      if (!enabled) return;
      const cleanField = field ? field.slice(0, 120) : null;
      const now = Date.now();
      // Throttle heartbeats unless the focused field changed.
      if (cleanField === lastPresenceFieldRef.current && now - lastPresenceSentAtRef.current < 7000) {
        return;
      }
      lastPresenceFieldRef.current = cleanField;
      lastPresenceSentAtRef.current = now;
      try {
        await api("/realtime/presence", {
          method: "POST",
          body: JSON.stringify({
            scope,
            resource_id: resourceId,
            field: cleanField,
          }),
        });
      } catch {
        // Non-blocking
      }
    },
    [enabled, scope, resourceId],
  );

  const clearEditing = useCallback(async () => {
    if (!enabled) return;
    lastPresenceFieldRef.current = null;
    lastPresenceSentAtRef.current = 0;
    try {
      await api(`/realtime/presence?scope=${encodeURIComponent(scope)}&resource_id=${encodeURIComponent(resourceId)}`, {
        method: "DELETE",
      });
    } catch {
      // Non-blocking
    }
  }, [enabled, scope, resourceId]);

  useEffect(() => {
    return () => {
      void clearEditing();
    };
  }, [clearEditing]);

  const otherEditors = useMemo(() => {
    const myId = user?.id || currentUserIdRef.current;
    return activeEditors.filter((ed) => !myId || ed.user_id !== myId);
  }, [activeEditors, user?.id]);

  const refreshNow = useCallback(async () => {
    const ev = pendingUpdate ?? {
      scope,
      resource_id: resourceId,
      summary: "Manual refresh",
      version: lastVersionRef.current,
      timestamp: new Date().toISOString(),
    };
    setPendingUpdate(null);
    await onRemoteUpdateRef.current?.(ev);
  }, [pendingUpdate, scope, resourceId]);

  const dismissPendingUpdate = useCallback(() => {
    setPendingUpdate(null);
  }, []);

  return {
    connected,
    otherEditors,
    pendingUpdate,
    reportEditing,
    clearEditing,
    refreshNow,
    dismissPendingUpdate,
  };
}
