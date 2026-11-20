"use client";

import { useEffect, useRef, useState } from "react";

export interface DropdownOption {
  value: string;
  label: string;
  icon?: React.ReactNode;
}

interface Props {
  label: string;
  value: string;
  options: DropdownOption[];
  onChange: (value: string) => void;
  className?: string;
}

/**
 * Menu déroulant stylé avec fermeture au clic extérieur / Échap.
 * L'option sélectionnée est affichée dans le déclencheur (avec son icône).
 */
export default function FilterDropdown({ label, value, options, onChange, className = "" }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === value) ?? options[0];

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        className="link-focus flex w-full items-center gap-2.5 rounded-xl border border-ink-700/70 bg-ink-900/70 px-3 py-2.5 text-left transition hover:border-ink-600 hover:bg-ink-800/70"
      >
        <span className="flex shrink-0 flex-col text-[9px] font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </span>
        <span className="h-5 w-px shrink-0 bg-ink-700" />
        <span className="flex min-w-0 flex-1 items-center gap-2">
          {selected?.icon ? <span className="flex shrink-0 items-center">{selected.icon}</span> : null}
          <span className="truncate text-[13px] font-medium text-slate-200">
            {selected?.label ?? "—"}
          </span>
        </span>
        <svg
          viewBox="0 0 24 24"
          className={`h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden
        >
          <path d="m6 9 6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open ? (
        <div
          role="listbox"
          className="absolute left-0 right-0 top-[calc(100%+6px)] z-50 max-h-72 overflow-y-auto rounded-xl border border-ink-700 bg-ink-900 p-1.5 shadow-2xl backdrop-blur-xl"
        >
          {options.map((option) => {
            const active = option.value === value;
            return (
              <button
                key={option.value}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => {
                  onChange(option.value);
                  setOpen(false);
                }}
                className={`link-focus flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13px] transition ${
                  active
                    ? "bg-accent/10 text-accent ring-1 ring-accent/20"
                    : "text-slate-300 hover:bg-ink-800 hover:text-slate-100"
                }`}
              >
                {option.icon ? <span className="flex shrink-0 items-center">{option.icon}</span> : null}
                <span className="min-w-0 flex-1 truncate">{option.label}</span>
                {active ? (
                  <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0" fill="none" stroke="currentColor" strokeWidth={2.2} aria-hidden>
                    <path d="m5 12 4 4L19 6" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                ) : null}
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}