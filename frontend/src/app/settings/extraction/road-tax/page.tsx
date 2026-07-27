"use client";

import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";

export default function RoadTaxPage() {
  return (
    <AppShell>
      <section className="grid gap-5">
        <div>
          <h1 className="text-3xl font-bold text-rl-textStrong">Road Tax</h1>
          <p className="mt-2">Manage road-tax rules by jurisdiction, vehicle class, and engine capacity.</p>
        </div>
        <SettingsNav />
        <div className="rl-panel p-5">
          <p className="text-rl-text">Road tax reference configuration will be available here.</p>
        </div>
      </section>
    </AppShell>
  );
}
