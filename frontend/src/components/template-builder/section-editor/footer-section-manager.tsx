"use client";

import { Input } from "@/components/ui/input";
import type { SectionFooterConfig } from "@/lib/template-section-compiler";

interface FooterSectionManagerProps {
  footer: SectionFooterConfig;
  onChange: (updatedFooter: SectionFooterConfig) => void;
}

export function FooterSectionManager({ footer, onChange }: FooterSectionManagerProps) {
  const handleChange = (field: keyof SectionFooterConfig, value: string) => {
    onChange({
      ...footer,
      [field]: value,
    });
  };

  return (
    <div className="space-y-4 text-xs">
      <div className="pb-3 border-b border-[var(--rl-border)]">
        <h4 className="text-sm font-bold text-[var(--rl-text-strong)]">
          Footer & Payment Specifications
        </h4>
        <p className="text-xs text-[var(--rl-text-muted)]">
          Configure agency bank details, payment instructions, and statutory quotation terms.
        </p>
      </div>

      <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 space-y-3">
        <h5 className="font-bold text-[var(--rl-text-strong)] text-xs uppercase tracking-wider text-neutral-500">
          Agency Bank Details
        </h5>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
              Bank Name
            </label>
            <Input
              value={footer.bankName || ""}
              onChange={(e) => handleChange("bankName", e.target.value)}
              placeholder="e.g. Hong Leong Bank"
            />
          </div>

          <div>
            <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
              Account Number
            </label>
            <Input
              value={footer.accountNo || ""}
              onChange={(e) => handleChange("accountNo", e.target.value)}
              placeholder="e.g. 12300318500"
            />
          </div>
        </div>

        <div>
          <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
            Account Holder Name
          </label>
          <Input
            value={footer.accountHolder || ""}
            onChange={(e) => handleChange("accountHolder", e.target.value)}
            placeholder="e.g. Risklocker Sdn. Bhd."
          />
        </div>
      </div>

      <div className="rounded-[var(--rl-radius)] border border-[var(--rl-border)] bg-[var(--rl-surface)] p-4 space-y-3">
        <h5 className="font-bold text-[var(--rl-text-strong)] text-xs uppercase tracking-wider text-neutral-500">
          Disclaimers & Notes
        </h5>

        <div>
          <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
            Terms & Conditions Disclaimer
          </label>
          <Input
            value={footer.termsNotice || ""}
            onChange={(e) => handleChange("termsNotice", e.target.value)}
            placeholder="e.g. *Terms and Condition Applied"
          />
        </div>

        <div>
          <label className="block font-semibold text-[var(--rl-text-strong)] mb-1">
            Payment Method Header
          </label>
          <Input
            value={footer.paymentNotice || ""}
            onChange={(e) => handleChange("paymentNotice", e.target.value)}
            placeholder="e.g. Payment Method"
          />
        </div>
      </div>
    </div>
  );
}
