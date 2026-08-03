"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Envelope, ShieldCheck } from "@phosphor-icons/react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) router.replace("/upload");
  }, [user, router]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
      router.replace("/upload");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
    } finally {
      setLoading(false);
    }
  }

  if (authLoading || user) {
    return (
      <main className="grid min-h-screen place-items-center bg-[var(--rl-bg)] px-5">
        <p className="text-sm text-[var(--rl-text-muted)]">Checking session…</p>
      </main>
    );
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[var(--rl-bg)] px-5 py-10">
      <div className="w-full max-w-[400px]">
        <div className="mb-8 text-center">
          <img
            src="/assets/brand/logo-black.png"
            alt="Risklocker"
            className="mx-auto h-10 w-auto"
          />
          <h1 className="mt-4 text-[24px] font-bold text-[var(--rl-text-strong)] font-[var(--font-manrope)]">
            Quotation System
          </h1>
          <p className="mt-1 text-[14px] text-[var(--rl-text-muted)]">Sign in to your account</p>
        </div>

        <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-6 shadow-card">
          <form onSubmit={submit} className="grid gap-5">
            <label className="grid gap-1.5">
              <span className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Email</span>
              <div className="relative">
                <Envelope
                  aria-hidden="true"
                  size={16}
                  weight="regular"
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]"
                />
                <Input
                  type="email"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  error={!!error}
                  required
                  autoFocus
                  className="pl-9"
                />
              </div>
            </label>

            <label className="grid gap-1.5">
              <span className="text-[13px] font-semibold text-[var(--rl-text-strong)]">Password</span>
              <div className="relative">
                <Lock
                  aria-hidden="true"
                  size={16}
                  weight="regular"
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--rl-text-muted)]"
                />
                <Input
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  error={!!error}
                  required
                  className="pl-9"
                />
              </div>
            </label>

            {error ? (
              <div className="flex items-center gap-2 rounded-[var(--rl-radius-sm)] bg-[var(--rl-red-light)] px-3 py-2.5 text-[13px] font-semibold text-[var(--rl-red)]">
                <ShieldCheck aria-hidden="true" size={16} weight="fill" />
                {error}
              </div>
            ) : null}

            <Button type="submit" loading={loading} size="md" className="w-full">
              Sign in
            </Button>
          </form>
        </div>
        <p className="mt-5 text-center text-[13px] text-[var(--rl-text-muted)]">
          Private staff access. There is no public registration.
        </p>
      </div>
    </main>
  );
}
