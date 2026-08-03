"use client";

import { useEffect, useState } from "react";
import { Plus, ArrowsClockwise, ArrowCounterClockwise, FloppyDisk } from "@phosphor-icons/react";
import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { apiErrorMessage } from "@/lib/errors";

type User = { id: string; email: string; role: string; status: string };

export default function SettingsUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("staff");
  const [error, setError] = useState("");
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
      await api("/users", { method: "POST", body: JSON.stringify({ email, password, role }) });
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

  const roleVariant = (r: string): "success" | "warning" | "info" => {
    if (r === "admin") return "success";
    if (r === "dev") return "warning";
    return "info";
  };

  return (
    <AppShell>
      <section className="grid gap-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-[30px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">Users</h1>
            <p className="text-[14px] text-[var(--rl-text-muted)]">Manage users and roles.</p>
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
            <h2 className="text-lg font-bold text-[var(--rl-text-strong)]">Users & Roles</h2>
            <div className="grid gap-4 sm:grid-cols-3">
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
                  <option value="dev">Dev</option>
                  <option value="admin">Admin</option>
                </Select>
              </div>
            </div>
            <div>
              <Button type="submit" icon={<Plus size={16} weight="bold" />}>Add user</Button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px]">
                <thead>
                  <tr>
                    <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Email</th>
                    <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Role</th>
                    <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Status</th>
                    <th className="px-4 py-2.5 text-left text-[12px] font-semibold text-[var(--rl-text-muted)] uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td className="px-4 py-2.5 text-[14px] font-medium text-[var(--rl-text-strong)]">{user.email}</td>
                      <td className="px-4 py-2.5 text-[14px]">
                        <Badge variant={roleVariant(user.role)}>{user.role}</Badge>
                      </td>
                      <td className="px-4 py-2.5 text-[14px]">
                        <Badge variant={user.status === "active" ? "success" : "default"}>{user.status}</Badge>
                      </td>
                      <td className="px-4 py-2.5 text-[14px]">
                        <Button variant="secondary" size="sm" icon={<ArrowCounterClockwise size={14} weight="bold" />} onClick={() => revokeSessions(user.id)}>
                          Revoke sessions
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </form>
        </Card>
      </section>
    </AppShell>
  );
}
