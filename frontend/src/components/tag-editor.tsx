"use client";

import { useRef, useState } from "react";
import { X } from "@phosphor-icons/react";

type TagEditorProps = {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  hint?: string;
  maxEntries?: number;
};

export function TagEditor({ label, values, onChange, placeholder, hint, maxEntries = 500 }: TagEditorProps) {
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const id = `tag-editor-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

  function commit() {
    const text = draft.trim();
    if (!text) return;
    if (values.length >= maxEntries) return;
    onChange([...values, text].filter((item, index, all) => all.indexOf(item) === index));
    setDraft("");
  }

  function remove(value: string) {
    onChange(values.filter((item) => item !== value));
  }

  return (
    <label className="grid gap-1 text-[12px] font-semibold text-[var(--rl-text-strong)]">
      <span>{label}</span>
      <span className="flex min-h-10 flex-wrap items-center gap-1.5 rounded-[var(--rl-radius-sm)] border border-[var(--rl-border)] bg-white px-2 py-1.5 transition-colors focus-within:border-[var(--rl-black)]">
        {values.map((value) => (
          <span key={value} className="inline-flex items-center gap-1 rounded-[var(--rl-radius-sm)] bg-[var(--rl-bg)] px-2 py-1 text-[12px] font-medium text-[var(--rl-text-strong)]">
            {value}
            <button
              type="button"
              aria-label={`Remove ${value}`}
              onClick={() => remove(value)}
              className="grid h-4 w-4 place-items-center rounded text-[var(--rl-text-muted)] hover:bg-[var(--rl-red-light)] hover:text-[var(--rl-red)]"
            >
              <X size={10} weight="bold" />
            </button>
          </span>
        ))}
        <input
          ref={inputRef}
          id={id}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              commit();
            } else if (event.key === "Backspace" && !draft && values.length) {
              remove(values[values.length - 1]);
            }
          }}
          onBlur={commit}
          placeholder={placeholder}
          disabled={values.length >= maxEntries}
          className="min-w-[120px] flex-1 bg-transparent px-1 py-1 text-[12px] font-normal outline-none placeholder:text-[var(--rl-text-muted)]"
        />
      </span>
      {hint ? <span className="text-[11px] font-normal text-[var(--rl-text-muted)]">{hint}</span> : null}
    </label>
  );
}
