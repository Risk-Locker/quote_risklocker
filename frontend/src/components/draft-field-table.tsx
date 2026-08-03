"use client";

import { memo, useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, Info } from "lucide-react";

type DraftField = {
  value?: string | null;
  status?: string;
  message?: string;
  warnings?: string[];
  evidence?: string;
};

type ReviewGroup = {
  id: string;
  title: string;
  collapsed?: boolean;
  fields: string[];
};

type ReviewSchema = {
  groups?: ReviewGroup[];
};

type EvidenceEntry = {
  value: string;
  score: number;
  source_method: string;
  page?: number | null;
  evidence: string;
};

const labels: Record<string, string> = {
  insurance_type: "Insurance Type",
  insurance_company: "Insurance Company",
  source_template_category: "Template Category",
  product_name: "Source Product",
  customer_name: "Customer Name",
  issue_date: "Issued Date",
  valid_until: "Valid Until",
  vehicle_no: "Vehicle No",
  vehicle_class: "Vehicle Class",
  car_brand: "Car Brand",
  car_model: "Car Model",
  vehicle_year: "Vehicle Year",
  engine_cc: "Capacity",
  engine_no: "Engine/Motor No",
  chassis_no: "Chassis No",
  cover_period: "Cover Period",
  coverage_type: "Coverage Type",
  coverage_amount: "Coverage Amount",
  market_value: "Market Value",
  agreed_value: "Agreed Value",
  excess_amount: "Excess Amount",
  basic_premium_vehicle: "Basic Premium (Vehicle)",
  basic_premium_trailer: "Basic Premium (Trailer)",
  premium: "Insurance Premium",
  ncd_amount: "NCD Amount",
  loading_amount: "Loading",
  all_riders_amount: "All Riders",
  optional_cover_amount: "Optional Cover Amount",
  service_tax: "Service Tax",
  stamp_duty: "Stamp Duty",
  gross_premium: "Gross Premium",
  roadtax: "Roadtax",
  service_fee: "Runner Fee",
  total_amount: "Total Premium",
  ncd_percent: "NCD",
  optional_covers: "Optional Covers",
  notes: "Notes"
};

const fallbackGroups: ReviewGroup[] = [
  {
    id: "quotation_values",
    title: "Quotation Values",
    fields: ["coverage_type", "cover_period", "car_model", "ncd_percent", "coverage_amount", "premium", "roadtax", "service_fee", "total_amount"]
  },
  {
    id: "source_details",
    title: "More Source Details",
    fields: ["insurance_company", "source_template_category", "product_name", "customer_name", "vehicle_no", "issued_date", "valid_until", "vehicle_year", "engine_cc", "engine_no", "chassis_no", "market_value", "agreed_value", "excess_amount", "basic_premium_vehicle", "ncd_amount", "service_tax", "stamp_duty", "gross_premium", "optional_cover_amount", "optional_covers", "notes"]
  }
];

const longFields = new Set(["optional_covers", "notes"]);

function truncate(text: string, max: number) {
  return text.length > max ? text.slice(0, max) + "\u2026" : text;
}

const EvidenceTag = memo(function EvidenceTag({
  fieldName,
  evidence,
  fieldHints,
  onFieldClick,
  active,
}: {
  fieldName: string;
  evidence?: EvidenceEntry[];
  fieldHints?: Record<string, string>;
  onFieldClick?: (field: string | null) => void;
  active?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  if (!evidence || !evidence.length) {
    if (!fieldHints?.[fieldName]) return null;
    return (
      <span
        className="inline-flex items-center gap-1 text-xs text-rl-text cursor-default select-none"
        title={fieldHints[fieldName]}
      >
        <Info aria-hidden="true" size={14} />
        Source
      </span>
    );
  }

  const primary = evidence[0];
  const snippet = truncate(primary.evidence, 50);
  const hasMultiple = evidence.length > 1;

  return (
    <div ref={ref} className="relative inline-flex">
      <button
        type="button"
        className={`inline-flex items-center gap-1 text-xs font-bold text-rl-blue hover:underline select-none ${active ? "ring-2 ring-[var(--rl-red)] ring-offset-1" : ""}`}
        onClick={(e) => {
          e.stopPropagation();
          onFieldClick?.(fieldName);
          setOpen(!open);
        }}
      >
        <Info aria-hidden="true" size={14} />
        {snippet || "Source"}
        {hasMultiple ? ` +${evidence.length - 1}` : null}
        {open ? <ChevronUp aria-hidden="true" size={12} /> : <ChevronDown aria-hidden="true" size={12} />}
      </button>
      {open ? (
        <div className="absolute bottom-full left-0 z-30 mb-2 w-80 rounded-md border border-rl-line bg-white p-3 shadow-lg text-xs">
          <div className="grid gap-2 max-h-64 overflow-auto">
            {evidence.map((c, i) => (
              <div key={i} className="rounded border border-rl-line bg-rl-soft p-2">
                <p className="break-words leading-relaxed">{c.evidence || "No evidence text"}</p>
                <p className="mt-1 text-rl-text">
                  Value: <span className="font-bold text-rl-textStrong">{c.value}</span>
                  {c.page != null ? ` \u00b7 Pg ${c.page}` : ""}
                  {c.score ? ` \u00b7 ${(c.score * 100).toFixed(0)}%` : ""}
                </p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
},
  (prev, next) =>
    prev.fieldName === next.fieldName &&
    JSON.stringify(prev.evidence) === JSON.stringify(next.evidence) &&
    prev.fieldHints?.[prev.fieldName] === next.fieldHints?.[next.fieldName]
);

const FieldEditor = memo(function FieldEditor({
  fieldName,
  field,
  hint,
  evidence,
  activeField,
  showEvidence,
  onFieldClick,
  onChange,
}: {
  fieldName: string;
  field: DraftField;
  hint?: string;
  evidence?: EvidenceEntry[];
  activeField?: string | null;
  showEvidence?: boolean;
  onFieldClick?: (field: string | null) => void;
  onChange: (field: string, value: string) => void;
}) {
  const label = labels[fieldName] || fieldName;
  const needsCheck = field.status === "check_needed";

  return (
    <div className={`flex flex-col gap-1.5 rounded-md border p-3 ${
      needsCheck ? "border-amber-300 bg-amber-50" : "border-rl-line bg-white"
    }`}>
      <div className="flex items-center justify-between gap-2">
        <label className="text-sm font-bold text-rl-textStrong" htmlFor={`field-${fieldName}`}>
          {label}
        </label>
        {showEvidence ? (
          <EvidenceTag
            fieldName={fieldName}
            evidence={evidence}
            fieldHints={hint ? { [fieldName]: hint } : undefined}
            onFieldClick={onFieldClick}
            active={activeField === fieldName}
          />
        ) : null}
      </div>
      {longFields.has(fieldName) ? (
        <textarea
          id={`field-${fieldName}`}
          className="rl-input min-h-[60px] resize-y"
          aria-invalid={needsCheck}
          value={field.value || ""}
          onChange={(event) => onChange(fieldName, event.target.value)}
        />
      ) : (
        <input
          id={`field-${fieldName}`}
          className="rl-input"
          aria-invalid={needsCheck}
          value={field.value || ""}
          onChange={(event) => onChange(fieldName, event.target.value)}
        />
      )}
      {needsCheck ? (
        <p className="text-xs font-bold text-rl-warning">Please check this value.</p>
      ) : null}
    </div>
  );
},
  (prev, next) =>
    prev.fieldName === next.fieldName &&
    prev.field.value === next.field.value &&
    prev.field.status === next.field.status &&
    prev.hint === next.hint &&
    prev.showEvidence === next.showEvidence &&
    prev.activeField === next.activeField &&
    JSON.stringify(prev.evidence) === JSON.stringify(next.evidence)
);

export const DraftFieldTable = memo(function DraftFieldTable({
  fields,
  reviewSchema,
  fieldHints,
  fieldEvidence,
  showEvidence,
  activeField,
  onFieldClick,
  onChange,
}: {
  fields: Record<string, DraftField>;
  reviewSchema?: ReviewSchema;
  fieldHints?: Record<string, string>;
  fieldEvidence?: Record<string, EvidenceEntry[]>;
  showEvidence?: boolean;
  activeField?: string | null;
  onFieldClick?: (field: string | null) => void;
  onChange: (field: string, value: string) => void;
}) {
  const groups = reviewSchema?.groups?.length ? reviewSchema.groups : fallbackGroups;
  return (
    <div className="grid gap-4">
      {groups.map((group) => {
        const content = (
          <div className="mt-3 grid gap-3">
            {group.fields.map((fieldName) => (
              <FieldEditor
                key={fieldName}
                fieldName={fieldName}
                field={fields[fieldName] || {}}
                hint={fieldHints?.[fieldName]}
                evidence={fieldEvidence?.[fieldName]}
                activeField={activeField}
                showEvidence={showEvidence}
                onFieldClick={onFieldClick}
                onChange={onChange}
              />
            ))}
          </div>
        );
        return (
          <section key={group.id} className="rl-panel p-4">
            <h2 className="text-lg font-bold text-rl-textStrong">{group.title}</h2>
            {content}
          </section>
        );
      })}
    </div>
  );
});
