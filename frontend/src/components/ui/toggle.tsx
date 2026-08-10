"use client";

type ToggleProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  description?: string;
};

export function Toggle({ checked, onChange, label, description }: ToggleProps) {
  const id = `toggle-${(label || "switch").replace(/\s+/g, "-").toLowerCase()}`;
  return (
    <div className="flex items-center gap-2.5">
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label || "Toggle"}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-[24px] w-[44px] shrink-0 cursor-pointer items-center rounded-full transition-colors duration-300
          ${checked ? "bg-[var(--rl-red)]" : "bg-[var(--rl-border)]"}`}
      >
        <span
          className={`inline-block h-[18px] w-[18px] transform rounded-full bg-white shadow-sm transition-transform duration-300
            ${checked ? "translate-x-[23px]" : "translate-x-[3px]"}`}
        />
      </button>
      {label ? (
        <label htmlFor={id} className="grid cursor-pointer">
          <span className={`text-[13px] font-semibold transition-colors ${checked ? "text-[var(--rl-text-strong)]" : "text-[var(--rl-text-muted)]"}`}>
            {label}
          </span>
          {description ? <span className="text-[11px] text-[var(--rl-text-muted)]">{description}</span> : null}
        </label>
      ) : null}
    </div>
  );
}
