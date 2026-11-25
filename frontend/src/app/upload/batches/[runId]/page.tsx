"use client";

import { use } from "react";
import { AppShell } from "@/components/app-shell";
import { StagingBatchArena } from "@/components/upload/StagingBatchArena";

export default function StagingBatchPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = use(params);
  return (
    <AppShell>
      <StagingBatchArena runId={runId} />
    </AppShell>
  );
}
