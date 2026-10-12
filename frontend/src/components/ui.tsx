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

export function Button({ children, onClick, disabled, kind = "primary", type = "button", title }: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; kind?: "primary" | "ghost" | "danger";
  type?: "button" | "submit"; title?: string;
}) {
  const kinds = {
    primary: "bg-accent text-bg hover:brightness-110",
    ghost: "border border-line text-ink hover:bg-pane-2",
    danger: "border border-bad text-bad hover:bg-bad/10",
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled} title={title}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${kinds[kind]}`}>
      {children}
    </button>
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
