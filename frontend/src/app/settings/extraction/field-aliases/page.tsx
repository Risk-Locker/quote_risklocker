"use client";

import { SettingsNav } from "@/components/settings-nav";
import { AppShell } from "@/components/app-shell";

export default function FieldAliasesPage() {
  return (
    <AppShell>
      <section className="grid gap-5">
        <div>
          <h1 className="text-3xl font-bold text-rl-textStrong">Field Aliases</h1>
          <p className="mt-2">Manage extraction synonyms so OCR can match more variants.</p>
        </div>
        <SettingsNav />
        <div className="rl-panel p-5">
          <p className="text-rl-text">Field aliases configuration will be available here.</p>
        </div>
      </section>
    </AppShell>
  );
}
