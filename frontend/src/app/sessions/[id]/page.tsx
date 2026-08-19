"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import { AppShell } from "@/components/app-shell";
import { ReviewPhase } from "@/components/session-workspace/review-phase";
import { PreviewPhase } from "@/components/session-workspace/preview-phase";

const SLIDE = {
  initial: { opacity: 0, x: 32 },
  animate: { opacity: 1, x: 0 },
  exit: { opacity: 0, x: -32 },
  transition: { duration: 0.22, ease: "easeOut" as const },
};

export default function SessionWorkspacePage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ step?: string }>;
}) {
  const { id } = use(params);
  const { step } = use(searchParams);
  const router = useRouter();
  const phase = step === "preview" ? "preview" : "review";

  return (
    <AppShell>
      <AnimatePresence mode="wait" initial={false}>
        {phase === "review" ? (
          <motion.div key="review" {...SLIDE}>
            <ReviewPhase id={id} onNext={() => router.push(`?step=preview`, { scroll: false })} />
          </motion.div>
        ) : (
          <motion.div key="preview" {...SLIDE}>
            <PreviewPhase id={id} onBack={() => router.push(`?step=review`, { scroll: false })} />
          </motion.div>
        )}
      </AnimatePresence>
    </AppShell>
  );
}
