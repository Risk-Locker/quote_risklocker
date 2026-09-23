"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { PageLoading } from "@/components/ui/page-loading";

export default function ClientRecordsRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/insights?tab=clients");
  }, [router]);

  return <PageLoading />;
}
