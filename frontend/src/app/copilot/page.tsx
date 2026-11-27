"use client";

import { AppShell } from "@/components/app-shell";
import { CopilotWorkspace } from "@/components/copilot/CopilotWorkspace";

export default function CopilotPage() {
  return (
    <AppShell>
      <div className="h-[calc(100vh-88px)] min-h-[560px] rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-white shadow-xs overflow-hidden">
        <CopilotWorkspace variant="fullscreen" />
      </div>
    </AppShell>
  );
}
