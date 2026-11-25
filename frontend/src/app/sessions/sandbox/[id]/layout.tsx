"use client";

import { use, type ReactNode } from "react";
import { SessionWorkspaceProvider } from "@/components/session-workspace/provider";

export default function SandboxSessionLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <SessionWorkspaceProvider sessionId={id}>{children}</SessionWorkspaceProvider>;
}
