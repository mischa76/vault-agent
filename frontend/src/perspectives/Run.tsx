import { useEffect, useState } from "react";
import { deriveStrip, deriveUsage, elapsedSeconds, formatDuration, formatTokens } from "../derive";
import type { GraphNode, ProjectCheck, Run, TraceEvent } from "../types";
import { StatusStrip } from "../components/StatusStrip";
import { Button, Dot, ErrorNote, KV, Pill, Section } from "../components/ui";

export function RunPerspective({ run, events, nodes, onReview, onCancel, onContinue, onDiscard, busy, check, onParse, parsing }: {
  run: Run; events: TraceEvent[]; nodes: GraphNode[]; onReview: () => void;
  onCancel: () => void; onContinue: () => void; onDiscard: () => void; busy: boolean;
  check?: ProjectCheck | null; onParse?: () => void; parsing?: boolean;
}) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    if (run.status !== "running") return;
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, [run.status]);
  const strip = deriveStrip(nodes, events, run.status);
  const usage = deriveUsage(events);
  const seconds = elapsedSeconds(run.started, run.finished, now);

  return (
    <div className="grid gap-4">
      <Section title="Pipeline" aside={<span className="flex items-center gap-2 text-sm"><Dot status={run.status} pulse /><span>{run.status}</span></span>}>
        <StatusStrip strip={strip} />
        <p className="mt-2 text-xs text-ink-faint">Derived from the run's trace: a node is done once a later node's call appears; dashed nodes make no model calls of their own and are inferred.</p>
        {run.status === "paused" ? (
          <div className="mt-3 flex items-center gap-3">
            <Button onClick={onReview}>Open the checkpoint</Button>
            <span className="text-xs text-ink-faint">the run waits for the human decision</span>
          </div>
        ) : null}
        {run.status === "running" ? (
          <div className="mt-3 flex items-center gap-3">
            <Button kind="danger" onClick={onCancel} disabled={busy}>Cancel the run</Button>
            <span className="text-xs text-ink-faint">the work so far stays checkpointed; the run can be continued or discarded afterwards</span>
          </div>
        ) : null}
        {run.status === "interrupted" || run.status === "crashed" ? (
          <div className="mt-3 flex items-center gap-3">
            <Button onClick={onContinue} disabled={busy}>Continue the run</Button>
            <Button kind="danger" onClick={onDiscard} disabled={busy}>Discard the run</Button>
            <span className="text-xs text-ink-faint">continues at the latest checkpoint — `vault-agent resume --out …` — or drops the thread</span>
          </div>
        ) : null}
        <div className="mt-3"><ErrorNote error={run.error} /></div>
      </Section>
      <div className="grid gap-4 md:grid-cols-2">
        <Section title="Usage (from the trace)">
          <KV rows={[
            ["Elapsed", formatDuration(seconds)],
            ["Calls", String(usage.calls)],
            ["Input tokens", `${formatTokens(usage.input)}${usage.cacheRead ? ` (${formatTokens(usage.cacheRead)} read from cache)` : ""}`],
            ["Output tokens", formatTokens(usage.output)],
            ["Errors / backstops", `${usage.errors} / ${usage.backstops}`],
            ["Models", usage.models.length ? usage.models.join(", ") : "–"],
          ]} />
          <p className="mt-2 text-xs text-ink-faint">Tokens, not money: the price table lives in the eval harness.</p>
        </Section>
        <Section title="Run">
          <KV rows={[
            ["Id", <code key="id" className="font-mono text-xs">{run.id}</code>],
            ["Thread", <code key="t" className="font-mono text-xs">{run.thread_id ?? "–"}</code>],
            ["Inputs", <span key="i" className="flex flex-wrap gap-1"><Pill>{run.requirements ?? "–"}</Pill>{run.schema ? <Pill>{run.schema}</Pill> : <Pill tone="warn">ungrounded</Pill>}{run.existing_run ? <Pill tone="info">extends {run.existing_run}</Pill> : null}{run.profiling ? <Pill>{run.profiling}</Pill> : null}{run.target_platform && run.target_platform !== "postgres" ? <Pill tone="info">{run.target_platform}</Pill> : null}</span>],
            ["Started", run.started ?? "–"], ["Finished", run.finished ?? "–"],
            ["Output", <code key="o" className="font-mono text-xs break-all">{run.out_dir}</code>],
          ]} />
        </Section>
      </div>
      <ProjectSection check={check ?? null} onParse={onParse} parsing={parsing ?? false} />
      <Section title="CLI equivalents">
        <p className="mb-2 text-xs text-ink-faint">Every action taken here is recorded as the command the terminal would run — a run driven from the workbench is replayable.</p>
        <pre className="overflow-auto rounded-md bg-pane-2 p-3 font-mono text-xs leading-5 whitespace-pre-wrap">{run.cli_equivalents.join("\n")}</pre>
        {run.checkpoints && run.checkpoints.length > 0 ? (
          <ul className="mt-2 text-xs text-ink-dim">
            {run.checkpoints.map((c, i) => <li key={i}><Pill tone={c.phase === "resolution" ? "info" : "warn"}>{c.phase}</Pill> <span className="font-mono">{c.command.length > 90 ? c.command.slice(0, 90) + "…" : c.command}</span></li>)}
          </ul>
        ) : null}
      </Section>
    </div>
  );
}

/** WP78: does the written project resolve, and does dbt parse it — reported, never gated. */
export function ProjectSection({ check, onParse, parsing }: { check: ProjectCheck | null; onParse?: () => void; parsing: boolean }) {
  if (!check || check.staging_models === 0) {
    return (
      <Section title="Project">
        <p className="text-xs text-ink-faint">No dbt project written yet — it appears once the run reaches the checkpoint.</p>
      </Section>
    );
  }
  const parse = check.parse;
  const dbt = check.dbt;
  return (
    <Section title="Project" aside={<span className="text-xs text-ink-faint">the written dbt project, checked without a warehouse</span>}>
      <KV rows={[
        ["Staging models", String(check.staging_models)],
        ["Resolves", check.unresolved.length === 0
          ? <Pill key="r" tone="ok">every stage reads a relation dbt can resolve</Pill>
          : <span key="r" className="flex flex-wrap gap-1"><Pill tone="bad">{check.unresolved.length} unresolved</Pill>{check.unresolved.map((n) => <code key={n} className="font-mono text-xs">{n}</code>)}</span>],
        ["To provide", check.inferred.length === 0
          ? <Pill key="i" tone="ok">none — every relation is declared</Pill>
          : <span key="i" className="flex flex-wrap gap-1"><Pill tone="warn">{check.inferred.length} inferred</Pill>{check.inferred.map((n) => <code key={n} className="font-mono text-xs">{n}</code>)}</span>],
        ["dbt", dbt ? `dbt-core ${dbt.version} with ${dbt.adapter}` : "not installed in the workbench's environment"],
      ]} />
      <div className="mt-3 flex items-center gap-3">
        <Button kind="ghost" onClick={onParse} disabled={parsing || !onParse || !dbt} title={dbt ? "dbt deps && dbt parse, keyless — no connection is opened" : "install the demo extra for dbt-postgres"}>
          {parsing ? "parsing…" : "dbt parse"}
        </Button>
        {parse ? (
          <span className="flex items-center gap-2 text-xs">
            <Pill tone={parse.status === "ok" ? "ok" : parse.status === "failed" ? "bad" : "warn"}>{parse.status}</Pill>
            <span className="text-ink-dim">{parse.adapter ? `${parse.adapter}, ${parse.seconds}s` : parse.detail ?? ""}</span>
          </span>
        ) : <span className="text-xs text-ink-faint">not parsed yet</span>}
      </div>
      {parse && parse.errors.length > 0 ? (
        <pre className="mt-2 overflow-auto rounded-md bg-pane-2 p-3 font-mono text-xs leading-5 whitespace-pre-wrap">{parse.errors.join("\n")}</pre>
      ) : null}
      <p className="mt-2 text-xs text-ink-faint">Unresolved: dbt cannot parse the project. Inferred: the project parses, the build fails on these until a human provides or maps the relation. The build itself belongs to your CI, not here.</p>
    </Section>
  );
}
