import type { StripEntry } from "../derive";

const LABELS: Record<string, string> = {
  orchestrator: "orchestrate", requirements_parser: "requirements", business_key_identifier: "business keys",
  data_contract: "contracts", entity_resolver: "resolve", link_proposer: "propose links",
  resolution_checkpoint: "resolution ✓", dv2_modeler: "model", code_generator: "generate",
  validator: "validate", source_mapper: "map sources", human_checkpoint: "human ✓", adr_author: "ADR",
};

const TONE = { pending: "border-line text-ink-faint", active: "border-accent text-accent bg-accent-soft", done: "border-ok/60 text-ok" };

export function StatusStrip({ strip }: { strip: StripEntry[] }) {
  return (
    <ol className="flex flex-wrap items-center gap-1" aria-label="pipeline status (derived from the trace)">
      {strip.map((n, i) => (
        <li key={n.id} className="flex items-center gap-1">
          <span
            className={`rounded-md border px-2 py-1 text-xs ${TONE[n.state]} ${n.inferred ? "border-dashed" : ""}`}
            title={`${n.id} — ${n.state}${n.inferred ? " (inferred: no model calls of its own)" : ""}${n.calls ? `, ${n.calls} call(s)` : ""}${n.attempts > 1 ? `, attempt ${n.attempts}` : ""}${n.errors ? `, ${n.errors} error(s)` : ""}${n.backstops ? `, ${n.backstops} backstop(s)` : ""}`}
            data-state={n.state}
          >
            {LABELS[n.id] ?? n.id}
            {n.attempts > 1 ? <sup className="ml-1 text-warn">×{n.attempts}</sup> : null}
            {n.errors ? <sup className="ml-1 text-bad">!</sup> : null}
          </span>
          {i < strip.length - 1 ? <span className="text-ink-faint">›</span> : null}
        </li>
      ))}
    </ol>
  );
}
