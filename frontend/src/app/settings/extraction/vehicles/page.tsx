"use client";

import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";

export default function VehiclesPage() {
  return (
    <AppShell>
      <section className="grid gap-5">
        <div>
          <h1 className="text-3xl font-bold text-rl-textStrong">Vehicles</h1>
          <p className="mt-2">Manage vehicle brand and model reference data with aliases.</p>
        </div>
        <SettingsNav />
        <div className="rl-panel p-5">
          <p className="text-rl-text">Vehicle reference configuration will be available here.</p>
        </div>
      </section>
    </AppShell>
  );
}
