import { useEffect, useState } from "react";
import { deriveStrip, deriveUsage, elapsedSeconds, formatDuration, formatTokens } from "../derive";
import type { GraphNode, Run, TraceEvent } from "../types";
import { StatusStrip } from "../components/StatusStrip";
import { Button, Dot, ErrorNote, KV, Pill, Section } from "../components/ui";

export function RunPerspective({ run, events, nodes, onReview }: {
  run: Run; events: TraceEvent[]; nodes: GraphNode[]; onReview: () => void;
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
            ["Inputs", <span key="i" className="flex flex-wrap gap-1"><Pill>{run.requirements ?? "–"}</Pill>{run.schema ? <Pill>{run.schema}</Pill> : <Pill tone="warn">ungrounded</Pill>}{run.existing_run ? <Pill tone="info">extends {run.existing_run}</Pill> : null}</span>],
            ["Started", run.started ?? "–"], ["Finished", run.finished ?? "–"],
            ["Output", <code key="o" className="font-mono text-xs break-all">{run.out_dir}</code>],
          ]} />
        </Section>
      </div>
      <Section title="CLI equivalents">
        <p className="mb-2 text-xs text-ink-faint">Every action taken here is recorded as the command the terminal would run — a run driven from the workbench is replayable.</p>
        <pre className="overflow-auto rounded-md bg-pane-2 p-3 font-mono text-xs leading-5 whitespace-pre-wrap">{run.cli_equivalents.join("\n")}</pre>
      </Section>
    </div>
  );
}
