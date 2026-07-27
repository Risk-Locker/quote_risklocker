"use client";

import { AppShell } from "@/components/app-shell";

export default function ClientRecordsPage() {
  return (
    <AppShell>
      <section className="grid gap-5">
        <div>
          <h1 className="text-3xl font-bold text-rl-textStrong">Client Records</h1>
          <p className="mt-2">Dashboard for confirmed quotations and client history.</p>
        </div>
        <div className="rl-panel p-5">
          <p className="text-rl-text">Client records dashboard will be available here.</p>
        </div>
      </section>
    </AppShell>
  );
}
