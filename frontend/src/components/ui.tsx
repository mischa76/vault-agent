import type { ReactNode } from "react";
import type { RunStatus } from "../types";

export const STATUS_TONE: Record<RunStatus, string> = {
  running: "bg-info", paused: "bg-warn", finished: "bg-ok", failed: "bg-bad", crashed: "bg-bad", discarded: "bg-ink-faint",
  interrupted: "bg-warn",
};

export function Dot({ status, pulse = false }: { status: RunStatus; pulse?: boolean }) {
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${STATUS_TONE[status]} ${pulse && status === "running" ? "animate-pulse" : ""}`}
      aria-label={status}
    />
  );
}

export function Pill({ children, tone = "line" }: { children: ReactNode; tone?: "line" | "accent" | "ok" | "warn" | "bad" | "info" }) {
  const tones = {
    line: "border-line text-ink-dim", accent: "border-accent text-accent", ok: "border-ok text-ok",
    warn: "border-warn text-warn", bad: "border-bad text-bad", info: "border-info text-info",
  };
  return <span className={`rounded-full border px-2 py-0.5 text-xs ${tones[tone]}`}>{children}</span>;
}

// WP141 (C45): the rule, owned here and written out in manual 14.4 —
//   primary  the one step that moves the project forward; at most one per perspective
//   add      adds something to the project and destroys nothing (attach, read, record, create)
//   danger   destroys or abandons, at every size (delete, discard, cancel)
//   ghost    navigation and toggles
export const BUTTON_KINDS = {
  primary: "bg-accent text-bg hover:brightness-110",
  add: "border border-accent text-accent hover:bg-accent-soft",
  danger: "border border-bad text-bad hover:bg-bad/10",
  ghost: "border border-line text-ink hover:bg-pane-2",
} as const;
export type ButtonKind = keyof typeof BUTTON_KINDS;
const BUTTON_SIZES = { md: "rounded-md px-3 py-1.5 text-sm", sm: "rounded px-1.5 py-0.5 text-xs" } as const;
const buttonClass = (kind: ButtonKind, size: keyof typeof BUTTON_SIZES) =>
  `${BUTTON_SIZES[size]} font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${BUTTON_KINDS[kind]}`;

export function Button({ children, onClick, disabled, kind = "primary", type = "button", title, size = "md", ariaLabel }: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; kind?: ButtonKind;
  type?: "button" | "submit"; title?: string; size?: keyof typeof BUTTON_SIZES; ariaLabel?: string;
}) {
  return (
    <button type={type} onClick={onClick} disabled={disabled} title={title} aria-label={ariaLabel}
      data-kind={kind} className={buttonClass(kind, size)}>
      {children}
    </button>
  );
}

/** A button of kind `add` that opens the file dialog: the label is the control, the hidden input
 * keeps its accessible name (WP141 — the attach controls were a grey label below every kind). */
export function FileButton({ children, accept, ariaLabel, onFile }: {
  children: ReactNode; accept: string; ariaLabel: string; onFile: (file: File) => void;
}) {
  return (
    <label data-kind="add" className={`cursor-pointer ${buttonClass("add", "md")} focus-within:ring-1 focus-within:ring-accent`}>
      <span aria-hidden="true">+ </span>{children}
      <input type="file" accept={accept} className="sr-only" aria-label={ariaLabel}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); e.target.value = ""; }} />
    </label>
  );
}

/** WP142 (C52): a decision between named answers — a radio group, every answer visible, the chosen
 * one filled, the default first. Never a checkbox whose word is its state. */
export function Choice<T extends string>({ label, options, value, onChange }: {
  label: string; options: readonly { value: T; label: string }[]; value: T; onChange: (value: T) => void;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="ml-auto inline-flex overflow-hidden rounded-md border border-line text-xs">
      {options.map((o) => (
        <button key={o.value} type="button" role="radio" aria-checked={o.value === value} onClick={() => onChange(o.value)}
          className={`px-2.5 py-1 font-medium transition ${o.value === value ? "bg-accent-soft text-accent" : "text-ink-dim hover:bg-pane hover:text-ink"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="rounded-lg border border-line bg-pane">
      <header className="flex items-center justify-between border-b border-line px-4 py-2">
        <h2 className="text-sm font-semibold tracking-wide text-ink-dim uppercase">{title}</h2>
        {aside}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-ink-faint">{children}</p>;
}

export function ErrorNote({ error }: { error: string | null }) {
  if (!error) return null;
  return <p role="alert" className="rounded-md border border-bad/50 bg-bad/10 px-3 py-2 text-sm text-bad">{error}</p>;
}

export function KV({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-sm">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-ink-faint">{k}</dt>
          <dd className="min-w-0 break-words text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
