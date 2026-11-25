"use client";

import { use } from "react";
import SessionWorkspacePage from "@/app/sessions/[id]/page";

export default function SandboxSessionWorkspacePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ step?: string }>;
}) {
  return <SessionWorkspacePage params={params} searchParams={searchParams} />;
}
