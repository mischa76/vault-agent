import { useMemo, useState } from "react";
import type { Checkpoint, Decision, ReviewItem, Run } from "../types";
import { Button, Empty, ErrorNote, Pill, Section } from "../components/ui";

const RESOLUTION_ANSWERS = ["NEW", "same_as_candidate", "unresolved"];

/** Decisions first, disclosures after (WP43's roles); within a role grouped by kind. */
export function groupItems(items: ReviewItem[]): { role: ReviewItem["role"]; kinds: { kind: string; items: ReviewItem[] }[] }[] {
  return (["decision", "disclosure"] as const).map((role) => {
    const map = new Map<string, ReviewItem[]>();
    for (const item of items) if (item.role === role) map.set(item.kind, [...(map.get(item.kind) ?? []), item]);
    return { role, kinds: [...map.entries()].map(([kind, items]) => ({ kind, items })) };
  });
}

export function ReviewPerspective({ run, checkpoint, onDecide, busy, error }: {
  run: Run; checkpoint: Checkpoint | null; onDecide: (d: Decision) => void; busy: boolean; error: string | null;
}) {
  const [owners, setOwners] = useState<Record<string, string>>({});
  const [resolutions, setResolutions] = useState<Record<string, string>>({});
  const [showDisclosures, setShowDisclosures] = useState(false);
  const groups = useMemo(() => groupItems(checkpoint?.items ?? []), [checkpoint]);

  if (run.status !== "paused") {
    return <Section title="Checkpoint"><Empty>the run is {run.status}; the checkpoint is only open while it is paused{run.status === "interrupted" || run.status === "crashed" ? " — continue or discard it from the Run tab" : ""}</Empty></Section>;
  }
  if (!checkpoint) return <Section title="Checkpoint"><Empty>loading the review queue…</Empty></Section>;

  const ownerItems = checkpoint.items.filter((i) => i.kind === "contract_owner" && i.asset);
  const ownersFilled = ownerItems.every((i) => (owners[i.asset!] ?? "").includes("<"));
  const decision = (accept: boolean): Decision => ({
    accept, owners: Object.fromEntries(Object.entries(owners).filter(([, v]) => v.trim())),
    resolutions: Object.fromEntries(Object.entries(resolutions).filter(([, v]) => v.trim())),
  });

  return (
    <div className="grid gap-4">
      <Section title="Checkpoint" aside={<span className="flex gap-2"><Pill tone="warn">{checkpoint.decisions} decisions</Pill><Pill>{checkpoint.disclosures} disclosures</Pill>{checkpoint.blocked ? <Pill tone="bad">blocked</Pill> : <Pill tone="ok">not blocked</Pill>}</span>}>
        <p className="text-sm text-ink-dim">{checkpoint.blocked ? "Something blocks agreement — a validation error or a contract without an owner. Answer the decisions, then accept, or discard the run." : "Nothing blocks agreement. Review the decisions and accept, or discard."}</p>
        <ErrorNote error={error} />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={() => onDecide(decision(true))} disabled={busy || (checkpoint.blocked && !ownersFilled)} title={checkpoint.blocked && !ownersFilled ? "every contract needs an owner as 'Name <email>' first" : undefined}>Accept and continue</Button>
          <Button kind="ghost" onClick={() => onDecide(decision(false))} disabled={busy} title="record owners and resolutions without accepting">Record without accepting</Button>
          <Button kind="danger" onClick={() => onDecide({ discard: true })} disabled={busy}>Discard the run</Button>
        </div>
      </Section>

      {checkpoint.unresolved.length > 0 ? (
        <Section title="Unresolved concepts (entity resolution)">
          <ul className="grid gap-3 text-sm">
            {checkpoint.unresolved.map((u) => (
              <li key={u.concept} className="grid gap-1 rounded-md border border-line p-3">
                <div className="flex items-center justify-between"><code className="font-mono">{u.concept}</code>
                  <input list="resolution-answers" value={resolutions[u.concept] ?? ""} placeholder="hub name, NEW, same_as_candidate, unresolved"
                    onChange={(e) => setResolutions({ ...resolutions, [u.concept]: e.target.value })}
                    className="w-72 rounded-md border border-line bg-pane-2 px-2 py-1 font-mono text-xs" aria-label={`resolution for ${u.concept}`} />
                </div>
                {u.evidence ? <p className="text-xs text-ink-faint whitespace-pre-wrap">{typeof u.evidence === "string" ? u.evidence : JSON.stringify(u.evidence)}</p> : null}
              </li>
            ))}
          </ul>
          <datalist id="resolution-answers">{RESOLUTION_ANSWERS.map((a) => <option key={a} value={a} />)}</datalist>
        </Section>
      ) : null}

      {groups.map((g) => (
        <Section key={g.role} title={g.role === "decision" ? "Decisions — these need an answer" : "Disclosures — what was assumed, inferred, dropped or declined"}
          aside={g.role === "disclosure" ? <button type="button" className="text-xs text-ink-dim underline" onClick={() => setShowDisclosures(!showDisclosures)}>{showDisclosures ? "hide" : "show"}</button> : null}>
          {g.kinds.length === 0 ? <Empty>none</Empty> : null}
          {(g.role === "decision" || showDisclosures) ? g.kinds.map((k) => (
            <details key={k.kind} open={g.role === "decision"} className="mb-2">
              <summary className="cursor-pointer text-sm"><span className="font-medium">{k.kind.replaceAll("_", " ")}</span> <span className="text-ink-faint">({k.items.length})</span></summary>
              <ul className="mt-2 grid gap-2">
                {k.items.map((item, i) => (
                  <li key={i} className="rounded-md border border-line bg-pane-2 p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      {item.asset ? <code className="font-mono text-xs text-accent">{item.asset}</code> : null}
                      <span>{item.summary}</span>
                      {item.source ? <Pill>{item.source}</Pill> : null}
                      {item.group && item.group !== "general" ? <Pill>{item.group}</Pill> : null}
                    </div>
                    {item.detail ? <p className="mt-1 text-xs text-ink-dim whitespace-pre-wrap">{item.detail}</p> : null}
                    {item.kind === "contract_owner" && item.asset ? (
                      <label className="mt-2 flex items-center gap-2 text-xs">
                        <span className="text-ink-faint">owner</span>
                        <input value={owners[item.asset] ?? ""} placeholder="Name <email>" aria-label={`owner for ${item.asset}`}
                          onChange={(e) => setOwners({ ...owners, [item.asset!]: e.target.value })}
                          className="w-72 rounded-md border border-line bg-pane px-2 py-1 font-mono" />
                      </label>
                    ) : null}
                  </li>
                ))}
              </ul>
            </details>
          )) : <Empty>{g.kinds.reduce((n, k) => n + k.items.length, 0)} items hidden</Empty>}
        </Section>
      ))}
    </div>
  );
}
