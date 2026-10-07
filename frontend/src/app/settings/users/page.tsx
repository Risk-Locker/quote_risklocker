"use client";

import { useEffect, useState } from "react";
import { Plus, ArrowsClockwise, ArrowCounterClockwise, Trash } from "@phosphor-icons/react";
import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Tooltip } from "@/components/ui/tooltip";
import { useToast } from "@/components/ui/toast";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type User = { id: string; name?: string | null; email: string; role: string; status: string };

export default function SettingsUsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("staff");
  const [error, setError] = useState("");
  const [targetUserToDelete, setTargetUserToDelete] = useState<User | null>(null);
  const [deleting, setDeleting] = useState(false);
  const { toast } = useToast();

  async function load() {
    const result = await api<{ users: User[] }>("/users");
    setUsers(result.users);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load users."));
  }, []);

  async function createUser(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await api("/users", { method: "POST", body: JSON.stringify({ name: name.trim() || undefined, email, password, role }) });
      setName("");
      setEmail("");
      setPassword("");
      toast("User created.", "success");
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    }
  }

  async function revokeSessions(userId: string) {
    try {
      await api(`/users/${userId}/sessions/revoke`, { method: "POST" });
      toast("Sessions revoked.", "success");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not revoke sessions.");
    }
  }

  async function handleDeleteUser() {
    if (!targetUserToDelete) return;
    setDeleting(true);
    try {
      await api(`/users/${targetUserToDelete.id}`, { method: "DELETE" });
      toast(`User ${targetUserToDelete.email} removed.`, "success");
      setTargetUserToDelete(null);
      await load();
    } catch (err) {
      setError(apiErrorMessage(err));
    } finally {
      setDeleting(false);
    }
  }

  const roleVariant = (r: string): "success" | "warning" | "info" => {
    if (r === "admin" || r === "super_admin") return "success";
    if (r === "dev") return "warning";
    return "info";
  };

  const isDev = currentUser?.role === "dev";

  const getDeleteRestriction = (targetUser: User): string | null => {
    if (targetUser.id === currentUser?.id) {
      return "Cannot delete your own active account";
    }
    if (isDev) {
      if (targetUser.role !== "staff") {
        return "Protected: Developers may only remove staff accounts";
      }
    }
    if (currentUser?.role === "admin" && targetUser.role === "super_admin") {
      return "Protected: Administrators cannot delete Super Admin accounts";
    }
    return null;
  };

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Users</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">Manage users, staff identities, and roles.</p>
          </div>
          <Button variant="secondary" icon={<ArrowsClockwise size={16} weight="bold" />} onClick={load}>
            Refresh
          </Button>
        </div>
        <SettingsNav />

        {error ? (
          <div className="rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">{error}</div>
        ) : null}

        <Card>
          <form className="grid gap-4 p-5" onSubmit={createUser}>
            <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Add Staff or User</h2>
            <div className="grid gap-4 sm:grid-cols-4">
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Staff Name</label>
                <Input placeholder="e.g. Nina or Alex" value={name} onChange={(event) => setName(event.target.value)} />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Email</label>
                <Input type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} required />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Password</label>
                <Input type="password" placeholder="Min 8 characters" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} />
              </div>
              <div className="grid gap-1.5">
                <label className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Role</label>
                <Select value={role} onChange={(event) => setRole(event.target.value)}>
                  <option value="staff">Staff</option>
                  {!isDev && <option value="dev">Dev</option>}
                  {!isDev && <option value="admin">Admin</option>}
                </Select>
              </div>
            </div>
            <div>
              <Button type="submit" icon={<Plus size={16} weight="bold" />}>Add user</Button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[620px]">
                <thead>
                  <tr>
                    <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Staff Name</th>
                    <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Email</th>
                    <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Role</th>
                    <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Status</th>
                    <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => {
                    const restriction = getDeleteRestriction(u);
                    const canDelete = !restriction;
                    return (
                      <tr key={u.id} className="border-t border-[var(--rl-border)]">
                        <td className="px-4 py-2.5 text-[14px] font-semibold text-[var(--rl-text-strong)]">
                          {u.name || <span className="text-[var(--rl-text-muted)] font-normal italic">No name</span>}
                        </td>
                        <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{u.email}</td>
                        <td className="px-4 py-2.5 text-[14px]">
                          <Badge variant={roleVariant(u.role)}>{u.role}</Badge>
                        </td>
                        <td className="px-4 py-2.5 text-[14px]">
                          <Badge variant={u.status === "active" ? "success" : "default"}>{u.status}</Badge>
                        </td>
                        <td className="px-4 py-2.5 text-[14px]">
                          <div className="flex items-center gap-2">
                            <Button
                              variant="secondary"
                              size="sm"
                              icon={<ArrowCounterClockwise size={14} weight="bold" />}
                              onClick={() => revokeSessions(u.id)}
                            >
                              Revoke
                            </Button>
                            {canDelete ? (
                              <Button
                                variant="danger"
                                size="sm"
                                icon={<Trash size={14} weight="bold" />}
                                onClick={() => setTargetUserToDelete(u)}
                              >
                                Remove
                              </Button>
                            ) : (
                              <Tooltip content={restriction || "Protected"}>
                                <span>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    disabled
                                    icon={<Trash size={14} weight="bold" />}
                                    className="opacity-40 cursor-not-allowed"
                                  >
                                    Remove
                                  </Button>
                                </span>
                              </Tooltip>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </form>
        </Card>
      </section>

      <ConfirmDialog
        open={Boolean(targetUserToDelete)}
        onOpenChange={(open) => !open && setTargetUserToDelete(null)}
        title="Remove User"
        message={`Are you sure you want to remove ${targetUserToDelete?.email}? This will revoke active sessions and permanently delete the user.`}
        confirmLabel="Remove User"
        loading={deleting}
        onConfirm={handleDeleteUser}
      />
    </AppShell>
  );
}
