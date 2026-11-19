"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export function useWhatsAppTester(
  tenureId: string,
  onNotify?: (type: "success" | "error", title: string, message: string) => void
) {
  const [copiedWhatsapp, setCopiedWhatsapp] = useState(false);
  const [isLoadingWhatsapp, setIsLoadingWhatsapp] = useState(false);

  const handleCopyWhatsapp = async () => {
    try {
      setIsLoadingWhatsapp(true);
      const json = await api<{ status: string; teaser_text: string }>(
        `/comparison/${tenureId}/whatsapp-teaser`
      );
      if (json?.teaser_text) {
        await navigator.clipboard.writeText(json.teaser_text);
        setCopiedWhatsapp(true);
        setTimeout(() => setCopiedWhatsapp(false), 3000);
      }
    } catch (err: any) {
      const msg = "Failed to copy WhatsApp summary: " + (err.message || String(err));
      if (onNotify) onNotify("error", "Copy Summary Failed", msg);
      else console.error(msg);
    } finally {
      setIsLoadingWhatsapp(false);
    }
  };

  return {
    copiedWhatsapp,
    isLoadingWhatsapp,
    handleCopyWhatsapp,
  };
}
