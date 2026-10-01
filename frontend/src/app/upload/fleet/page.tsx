"use client";

import { Suspense } from "react";
import { CircleNotch } from "@phosphor-icons/react";
import { AppShell } from "@/components/app-shell";
import { UploadWorkspace } from "@/components/upload/upload-workspace";

export default function FleetUploadPage() {
  return (
    <AppShell>
      <Suspense
        fallback={
          <div className="flex h-96 items-center justify-center">
            <CircleNotch className="size-8 animate-spin text-slate-400" />
          </div>
        }
      >
        <UploadWorkspace defaultMode="bulk" />
      </Suspense>
    </AppShell>
  );
}
