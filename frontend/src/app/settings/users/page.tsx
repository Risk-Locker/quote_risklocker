"use client";

import { useEffect, useState } from "react";
import { Plus, RefreshCw, RotateCcw } from "lucide-react";
import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";
import { api } from "@/lib/api";

type User = { id: string; email: string; role: string; status: string };

export default function SettingsUsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("staff");
  const [error, setError] = useState("");

  async function load() {
    const result = await api<{ users: User[] }>("/users");
    setUsers(result.users);
  }

  useEffect(() => {
    load().catch((err) => setError(err instanceof Error ? err.message : "Could not load users."));
  }, []);

  async function createUser(event: React.FormEvent) {
    event.preventDefault();
    await api("/users", { method: "POST", body: JSON.stringify({ email, password, role }) });
    setEmail("");
    setPassword("");
    await load();
  }

  async function revokeSessions(userId: string) {
    try {
      await api(`/users/${userId}/sessions/revoke`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not revoke sessions.");
    }
  }

  return (
    <AppShell>
      <section className="grid gap-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-bold text-rl-textStrong">Users</h1>
            <p className="mt-2">Manage users and roles.</p>
          </div>
          <button className="rl-button rl-button-secondary" type="button" onClick={load}>
            <RefreshCw aria-hidden="true" size={18} />
            Refresh
          </button>
        </div>
        <SettingsNav />
        {error ? <p className="rounded-md border border-rl-red bg-red-50 p-3 font-bold text-rl-red">{error}</p> : null}
        <form className="rl-panel grid gap-3 p-5" onSubmit={createUser}>
          <h2 className="text-xl font-bold text-rl-textStrong">Users & Roles</h2>
          <input className="rl-input" type="email" placeholder="Email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          <input className="rl-input" type="password" placeholder="Password (min 8 characters)" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={8} />
          <select className="rl-input" value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="staff">Staff</option>
            <option value="dev">Dev</option>
            <option value="admin">Admin</option>
          </select>
          <button className="rl-button w-fit" type="submit"><Plus aria-hidden="true" size={18} />Add user</button>
          <div className="overflow-x-auto">
            <table className="rl-table min-w-[520px]">
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td className="font-bold text-rl-textStrong">{user.email}</td>
                    <td>{user.role}</td>
                    <td>{user.status}</td>
                    <td>
                      <button className="rl-button rl-button-secondary" type="button" onClick={() => revokeSessions(user.id)}>
                        <RotateCcw aria-hidden="true" size={16} />
                        Revoke sessions
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </form>
      </section>
    </AppShell>
  );
}
