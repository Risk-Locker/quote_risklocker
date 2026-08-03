"use client";

import { useEffect, useState } from "react";
import { Bell, ShieldCheck, UserCheck, EnvelopeOpen } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";
import { useToast } from "@/components/ui/toast";

type NotificationItem = {
  id: string;
  event_type: string;
  title: string;
  body: string;
  read_at: string | null;
  delivery_state: string;
  created_at: string;
};

const EVENT_ICONS: Record<string, typeof Bell> = {
  invitation: Bell,
  role_change: ShieldCheck,
  status_change: UserCheck,
};

function iconFor(event_type: string) {
  const Icon = EVENT_ICONS[event_type] || Bell;
  return <Icon size={18} weight="bold" />;
}

export default function InboxPage() {
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [markingAll, setMarkingAll] = useState(false);
  const [marking, setMarking] = useState<Set<string>>(new Set());
  const { toast } = useToast();

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await api<{ notifications: NotificationItem[] }>("/notifications");
      setNotifications(result.notifications);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load notifications.");
    } finally {
      setLoading(false);
    }
  }

  async function markOneRead(id: string) {
    setMarking((prev) => new Set(prev).add(id));
    setError("");
    try {
      await api(`/notifications/${id}/read`, { method: "PATCH" });
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, read_at: new Date().toISOString() } : n)),
      );
      toast("Marked as read.", "success");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setMarking((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  }

  async function markAllRead() {
    setMarkingAll(true);
    setError("");
    try {
      await api("/notifications/read", { method: "PATCH" });
      const now = new Date().toISOString();
      setNotifications((prev) =>
        prev.map((n) => (n.read_at ? n : { ...n, read_at: now })),
      );
      const unreadCount = notifications.filter((n) => !n.read_at).length;
      toast(`${unreadCount} notification${unreadCount !== 1 ? "s" : ""} marked as read.`, "success");
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setMarkingAll(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const unreadCount = notifications.filter((n) => !n.read_at).length;

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Inbox</h1>
            <p className="mt-2 text-[14px] text-[var(--rl-text-muted)]">Account notifications, invitations, and role updates.</p>
          </div>
          {unreadCount > 0 && (
            <Button
              variant="secondary"
              loading={markingAll}
              icon={<EnvelopeOpen aria-hidden="true" size={18} weight="bold" />}
              onClick={markAllRead}
            >
              Mark all read
            </Button>
          )}
        </div>

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
            {error}
          </div>
        ) : null}

        {loading ? (
          <p className="text-[14px] font-semibold text-[var(--rl-text-strong)]">Loading notifications...</p>
        ) : notifications.length === 0 ? (
          <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-10 text-center">
            <p className="font-semibold text-[var(--rl-text-strong)]">No notifications yet.</p>
            <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">Invitations and account updates will appear here.</p>
          </div>
        ) : (
          <div className="grid gap-3">
            {notifications.map((item) => {
              const read = Boolean(item.read_at);
              return (
                <Card
                  key={item.id}
                  className={`flex items-start gap-4 p-4 ${read ? "" : "border-l-4 border-l-[var(--rl-black)]"}`}
                >
                  <span
                    className={`mt-0.5 flex-none rounded-[var(--rl-radius-sm)] p-2 ${
                      read ? "text-[var(--rl-text)] bg-[var(--rl-bg)]" : "text-white bg-[var(--rl-black)]"
                    }`}
                  >
                    {iconFor(item.event_type)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-[var(--rl-text-strong)]">
                        {item.title}
                      </span>
                      {item.delivery_state === "failed" && (
                        <Badge variant="danger">Email delivery failed</Badge>
                      )}
                    </div>
                    <p className="mt-1 text-[14px] text-[var(--rl-text)]">{item.body}</p>
                    <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">
                      {new Date(item.created_at).toLocaleString()}
                    </p>
                  </div>
                  {!read ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<EnvelopeOpen aria-hidden="true" size={16} weight="bold" />}
                      onClick={() => markOneRead(item.id)}
                      loading={marking.has(item.id)}
                      aria-label="Mark as read"
                    >
                      <span className="hidden sm:inline">Read</span>
                    </Button>
                  ) : (
                    <span className="flex-none p-2 text-[var(--rl-text-muted)]" aria-label="Read">
                      <EnvelopeOpen aria-hidden="true" size={18} weight="regular" />
                    </span>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </section>
    </AppShell>
  );
}
