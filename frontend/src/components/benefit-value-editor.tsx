"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";

export type TypedValue = Record<string, unknown> | null;

export function typedValueToString(value: TypedValue): string {
  if (!value) return "";
  const type = String(value.type || "");
  if (type === "distance") {
    if (value.unlimited) return "Unlimited";
    return `${value.value ?? ""} ${value.unit || "km"}`.trim();
  }
  if (type === "money") {
    return value.value != null && value.value !== "" ? `RM ${value.value}` : "";
  }
  if (type === "duration") {
    return `${value.value ?? ""} ${value.unit || "years"}`.trim();
  }
  if (type === "per_day") {
    return `RM ${value.value ?? ""} / day (${value.max_days ?? 1} days)`;
  }
  if (type === "custom") {
    return String(value.display_text || "");
  }
  return String(value.value ?? value.display_text ?? "");
}

export function parseValueString(text: string): TypedValue {
  const trimmed = text.trim();
  if (!trimmed) return null;

  if (/^unlimited(\s+km)?$/i.test(trimmed)) {
    return { type: "distance", value: null, unit: "km", unlimited: true };
  }

  // Money: "RM 300", "RM300", "300.00", "MYR 1,500"
  const moneyMatch = trimmed.match(/^(?:RM|MYR)?\s*(\d+(?:,\d+)*(?:\.\d+)?)$/i);
  if (moneyMatch && /RM|MYR/i.test(trimmed)) {
    const numStr = moneyMatch[1].replace(/,/g, "");
    return { type: "money", value: numStr, currency: "MYR", semantic_role: "insured_limit" };
  }

  // Distance: "50 km", "150km"
  const distMatch = trimmed.match(/^(\d+(?:,\d+)*(?:\.\d+)?)\s*(?:km|kilometres?|kilometers?)$/i);
  if (distMatch) {
    const numStr = distMatch[1].replace(/,/g, "");
    return { type: "distance", value: numStr, unit: "km", unlimited: false };
  }

  // Duration: "3 years", "12 months"
  const durMatch = trimmed.match(/^(\d+)\s*(years?|months?|days?|weeks?)$/i);
  if (durMatch) {
    return { type: "duration", value: durMatch[1], unit: durMatch[2].toLowerCase() };
  }

  // Number only -> default money
  if (/^\d+(?:,\d+)*(?:\.\d+)?$/.test(trimmed)) {
    return { type: "money", value: trimmed.replace(/,/g, ""), currency: "MYR", semantic_role: "insured_limit" };
  }

  // Fallback to custom
  return { type: "custom", display_text: trimmed };
}

export function typedValueLabel(value: TypedValue): string {
  return typedValueToString(value);
}

type BenefitValueEditorProps = {
  value: TypedValue;
  onChange: (value: TypedValue) => void;
  placeholder?: string;
  className?: string;
};

export function BenefitValueEditor({
  value,
  onChange,
  placeholder = 'e.g. RM300, 50 km, Unlimited, 3 years',
  className,
}: BenefitValueEditorProps) {
  const [text, setText] = useState<string>(() => typedValueToString(value));

  useEffect(() => {
    setText(typedValueToString(value));
  }, [value]);

  function handleChange(val: string) {
    setText(val);
    onChange(parseValueString(val));
  }

  return (
    <Input
      id="benefit-value-input"
      aria-label="Benefit value"
      value={text}
      onChange={(e) => handleChange(e.target.value)}
      placeholder={placeholder}
      className={className}
    />
  );
}
