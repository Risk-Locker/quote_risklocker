"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Mail, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      router.replace("/upload");
    }
  }, [user, router]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      router.replace("/upload");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
    } finally {
      setLoading(false);
    }
  }

  if (authLoading || user) {
    return (
      <main className="grid min-h-screen place-items-center bg-rl-soft px-5 py-10">
        <p className="text-sm text-rl-text">Checking session…</p>
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center bg-rl-soft px-5 py-10">
      <section className="w-full max-w-md" aria-labelledby="login-title">
        <div className="mb-5 flex items-center gap-3 px-1">
          <div className="grid size-11 place-items-center rounded-md bg-rl-black text-white" aria-hidden="true">
            <ShieldCheck size={24} />
          </div>
          <div>
            <p className="text-sm font-bold uppercase tracking-wide text-rl-red">Risklocker</p>
            <h1 id="login-title" className="text-2xl font-bold text-rl-textStrong">Quotation Converter</h1>
          </div>
        </div>

        <form className="rl-panel p-6 shadow-sm" onSubmit={submit}>
          <div>
            <h2 className="text-xl font-bold text-rl-textStrong">Sign in</h2>
            <p className="mt-1 text-sm">Enter your account email and password.</p>
          </div>

          <div className="mt-6 grid gap-4">
            <label className="grid gap-2 font-bold text-rl-textStrong">
              Email
              <span className="relative">
                <Mail className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-rl-text" aria-hidden="true" size={18} />
                <input
                  className="rl-input pl-10"
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  aria-invalid={Boolean(error)}
                  required
                  autoFocus
                />
              </span>
            </label>

            <label className="grid gap-2 font-bold text-rl-textStrong">
              Password
              <span className="relative">
                <Lock className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-rl-text" aria-hidden="true" size={18} />
                <input
                  className="rl-input pl-10"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  aria-invalid={Boolean(error)}
                  required
                />
              </span>
            </label>

            {error ? <p role="alert" className="rounded-md border border-rl-red bg-red-50 p-3 font-bold text-rl-red">{error}</p> : null}

            <button className="rl-button w-full" disabled={loading} type="submit">
              <Lock aria-hidden="true" size={18} />
              {loading ? "Signing in" : "Sign in"}
            </button>
          </div>
        </form>
        <p className="mt-4 px-2 text-center text-sm">Private staff access. There is no public registration.</p>
      </section>
    </main>
  );
}
