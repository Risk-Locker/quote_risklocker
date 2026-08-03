"use client";

import { Toaster } from "@/components/ui/toast";

export function Providers({ children }: { children: React.ReactNode }) {
  return <Toaster>{children}</Toaster>;
}
