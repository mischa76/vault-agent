import { useMemo, useState } from "react";
import type { Checkpoint, Decision, ReviewItem, Run, StageBinding } from "../types";
import { Button, Empty, ErrorNote, Pill, Section } from "../components/ui";

const FALLBACK_ANSWERS = ["NEW", "same_as_candidate", "unresolved"];

/** Decisions first, disclosures after (WP43's roles); within a role grouped by kind. */
export function groupItems(items: ReviewItem[]): { role: ReviewItem["role"]; kinds: { kind: string; items: ReviewItem[] }[] }[] {
  return (["decision", "disclosure"] as const).map((role) => {
    const map = new Map<string, ReviewItem[]>();
    for (const item of items) if (item.role === role) map.set(item.kind, [...(map.get(item.kind) ?? []), item]);
    return { role, kinds: [...map.entries()].map(([kind, items]) => ({ kind, items })) };
  });
}

// WP87: what the CLI's `_parse_owner` stores as name and address — `Name <email>`, or a bare address
// (its local part becomes the name). Anything else would be stored as a name without an address.
const BARE_EMAIL = /^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/;
export function ownerValid(value: string): boolean {
  const v = value.trim();
  return BARE_EMAIL.test(v) || /^[^<>]+<[^<>@\s]+@[^<>\s]+>$/.test(v);
}

// WP82: the aliases field — `STAGE_COLUMN=column, …`, the CLI's `--bind "STAGE=RELATION(…)"` inside the
// parentheses. `null` when a part is not `a=b`; the field says so and sends nothing for the stage.
export function parseAliases(text: string): Record<string, string> | null {
  const columns: Record<string, string> = {};
  for (const part of text.split(",")) {
    if (!part.trim()) continue;
    const m = /^\s*([^=\s,]+)\s*=\s*([^=\s,]+)\s*$/.exec(part);
    if (!m) return null;
    columns[m[1]!] = m[2]!;
  }
  return columns;
}

export function ReviewPerspective({ run, checkpoint, onDecide, busy, error }: {
  run: Run; checkpoint: Checkpoint | null; onDecide: (d: Decision) => void; busy: boolean; error: string | null;
}) {
  const [owners, setOwners] = useState<Record<string, string>>({});
  const [resolutions, setResolutions] = useState<Record<string, string>>({});
  const [links, setLinks] = useState<Record<string, boolean>>({});
  const [bindings, setBindings] = useState<Record<string, { relation: string; aliases: string }>>({}); // WP82
  const [mappings, setMappings] = useState<Record<string, string>>({}); // WP82: --map
  const [showDisclosures, setShowDisclosures] = useState(false);
  const groups = useMemo(() => groupItems(checkpoint?.items ?? []), [checkpoint]);

  if (run.status !== "paused") {
    return <Section title="Checkpoint"><Empty>the run is {run.status}; the checkpoint is only open while it is paused{run.status === "interrupted" || run.status === "crashed" ? " — continue or discard it from the Run tab" : ""}</Empty></Section>;
  }
  if (!checkpoint) return <Section title="Checkpoint"><Empty>loading the review queue…</Empty></Section>;

  const atResolution = checkpoint.phase === "resolution";
  const answers = checkpoint.answers?.length ? checkpoint.answers : FALLBACK_ANSWERS;
  const ownerItems = atResolution ? [] : checkpoint.items.filter((i) => i.kind === "contract_owner" && i.asset);
  const ownersFilled = ownerItems.every((i) => ownerValid(owners[i.asset!] ?? ""));
  const declined = Object.values(links).filter((v) => v === false).length;
  const pendingBindings = atResolution ? [] : (checkpoint.bindings ?? []);
  const boundStages = (): Record<string, StageBinding> => {
    const out: Record<string, StageBinding> = {};
    for (const [stage, b] of Object.entries(bindings)) {
      if (!b.relation.trim()) continue;
      const columns = parseAliases(b.aliases);
      if (columns === null) continue; // the field says it is malformed; nothing is sent for it
      out[stage] = { relation: b.relation.trim(), columns };
    }
    return out;
  };
  const decision = (accept: boolean): Decision => ({
    accept,
    owners: atResolution ? {} : Object.fromEntries(Object.entries(owners).filter(([, v]) => v.trim())),
    resolutions: Object.fromEntries(Object.entries(resolutions).filter(([, v]) => v.trim())),
    links: atResolution ? links : {},
    bindings: atResolution ? {} : boundStages(),
    mappings: atResolution ? {} : Object.fromEntries(Object.entries(mappings).filter(([, v]) => v.trim())),
  });

  return (
    <div className="grid gap-4">
      <Section title={atResolution ? "Resolution checkpoint — before the modeler" : "Sign-off checkpoint"}
        aside={<span className="flex gap-2">
          {atResolution ? <><Pill tone="warn">{checkpoint.links.length} proposals</Pill><Pill tone="warn">{checkpoint.resolutions.length} resolutions</Pill></>
            : <><Pill tone="warn">{checkpoint.decisions} decisions</Pill><Pill>{checkpoint.disclosures} disclosures</Pill>{checkpoint.blocked ? <Pill tone="bad">blocked</Pill> : <Pill tone="ok">not blocked</Pill>}</>}
        </span>}>
        <p className="text-sm text-ink-dim">
          {atResolution
            ? "The run paused before the model is built: declared keys and entity resolutions need a decision that steers the modeler. Everything left as proposed is ratified by accept — the CLI's --accept. Owners and the model's review come at sign-off, after the modeler."
            : checkpoint.blocked ? "Something blocks agreement — a validation error or a contract without an owner. Answer the decisions, then accept, or discard the run." : "Nothing blocks agreement. Review the decisions and accept, or discard."}
        </p>
        <ErrorNote error={error} />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={() => onDecide(decision(true))} disabled={busy || (!atResolution && checkpoint.blocked && !ownersFilled)} title={!atResolution && checkpoint.blocked && !ownersFilled ? "every contract needs an owner: 'Name <email>' or an email address" : undefined}>
            {atResolution ? (declined ? `Ratify the rest, decline ${declined}, and build the model` : "Ratify as proposed and build the model") : "Accept and continue"}
          </Button>
          {!atResolution ? <Button kind="ghost" onClick={() => onDecide(decision(false))} disabled={busy} title={checkpoint.blocked ? "record owners and resolutions without accepting; the run stays paused" : "record owners and resolutions without accepting — nothing blocks, so the run finishes"}>Record without accepting</Button> : null}
          <Button kind="danger" onClick={() => onDecide({ discard: true })} disabled={busy}>Discard the run</Button>
        </div>
      </Section>

      {atResolution && checkpoint.links.length > 0 ? (
        <Section title="Declared keys — links, relationship tables and key licenses">
          <p className="mb-2 text-xs text-ink-faint">Proposed from the source's own foreign keys. Build is the default, as in the CLI's prompt (`--link`); decline is the exception (`--no-link`). A license builds nothing: it allows the translation or alias the modeler will need.</p>
          <ul className="grid gap-2 text-sm">
            {checkpoint.links.map((l) => {
              const build = links[l.key] !== false;
              return (
                <li key={l.key} className="rounded-md border border-line bg-pane-2 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="font-mono text-xs text-accent">{l.key}</code>
                    <span>→ {l.target}</span>
                    <Pill>{l.kind}</Pill>
                    <label className="ml-auto flex items-center gap-2 text-xs">
                      <input type="checkbox" checked={build} aria-label={`build ${l.key}`}
                        onChange={(e) => setLinks({ ...links, [l.key]: e.target.checked })} />
                      {build ? (l.kind === "license" ? "allow" : "build") : "decline"}
                    </label>
                  </div>
                  <p className="mt-1 text-xs text-ink-dim">{l.note}</p>
                  {l.evidence.map((e, i) => <p key={i} className="text-xs text-ink-faint">{e}</p>)}
                </li>
              );
            })}
          </ul>
        </Section>
      ) : null}

      {atResolution && checkpoint.resolutions.length > 0 ? (
        <Section title="Entity resolutions — is the new concept something the vault already holds?">
          <ul className="grid gap-3 text-sm">
            {checkpoint.resolutions.map((p) => (
              <li key={p.concept} className="grid gap-1 rounded-md border border-line bg-pane-2 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span><code className="font-mono text-accent">{p.label}</code>{p.entity ? <span className="text-ink-faint"> (from {p.entity})</span> : null}: proposed {p.claim} <span className="text-ink-faint">({p.category}, confidence {p.confidence.toFixed(2)})</span></span>
                  <input list="resolution-answers" value={resolutions[p.concept] ?? ""} placeholder="leave as proposed, or NEW / a construct"
                    onChange={(e) => setResolutions({ ...resolutions, [p.concept]: e.target.value })}
                    className="w-72 rounded-md border border-line bg-pane px-2 py-1 font-mono text-xs" aria-label={`resolution for ${p.concept}`} />
                </div>
                {p.evidence.map((e, i) => <p key={i} className="text-xs text-ink-faint">{e}</p>)}
              </li>
            ))}
          </ul>
          <datalist id="resolution-answers">{answers.map((a) => <option key={a} value={a} />)}</datalist>
        </Section>
      ) : null}

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
          <datalist id="resolution-answers">{answers.map((a) => <option key={a} value={a} />)}</datalist>
        </Section>
      ) : null}

      {pendingBindings.length > 0 ? (
        <Section title="Stage bindings — relations no rule could bind">
          <p className="text-xs text-ink-dim">Each stage below reads a relation that does not exist until someone provides it. Name the declared relation it should read — the CLI's <code className="font-mono">--bind</code> — and, where the relation carries a key under another name, the alias <code className="font-mono">STAGE_COLUMN=column</code>. Left empty, the stage stays inferred and the review queue says so.</p>
          <ul className="mt-2 grid gap-2">
            {pendingBindings.map((b) => {
              const value = bindings[b.stage] ?? { relation: "", aliases: "" };
              const malformed = value.aliases.trim() !== "" && parseAliases(value.aliases) === null;
              return (
                <li key={b.stage} className="rounded-md border border-line bg-pane-2 p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="font-mono text-xs text-accent">{b.stage}</code>
                    <span>reads</span>
                    <code className="font-mono text-xs">{b.reads}</code>
                    <Pill tone={b.role === "decision" ? "warn" : "line"}>{b.reason}</Pill>
                  </div>
                  <p className="mt-1 text-xs text-ink-dim">
                    {b.reason === "rejected" && b.tried ? `the rule tried ${b.tried} and was refused: it lacks a column the stage hashes. ` : null}
                    the relation must carry: {b.expected_columns.join(", ")}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                    <label className="flex items-center gap-2">
                      <span className="text-ink-faint">relation</span>
                      <input value={value.relation} placeholder="declared relation" aria-label={`relation for ${b.stage}`}
                        onChange={(e) => setBindings({ ...bindings, [b.stage]: { ...value, relation: e.target.value } })}
                        className="w-56 rounded-md border border-line bg-pane px-2 py-1 font-mono" />
                    </label>
                    <label className="flex items-center gap-2">
                      <span className="text-ink-faint">aliases</span>
                      <input value={value.aliases} placeholder="STAGE_COLUMN=column, …" aria-label={`column aliases for ${b.stage}`}
                        onChange={(e) => setBindings({ ...bindings, [b.stage]: { ...value, aliases: e.target.value } })}
                        className="w-96 rounded-md border border-line bg-pane px-2 py-1 font-mono" />
                    </label>
                    {malformed ? <span className="text-bad">STAGE_COLUMN=column, separated by commas</span> : null}
                  </div>
                </li>
              );
            })}
          </ul>
        </Section>
      ) : null}

      {groups.filter((g) => !atResolution || g.role === "disclosure").map((g) => (
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
                    {!atResolution && item.kind === "mapping_unresolved" && item.asset ? (
                      <label className="mt-2 flex items-center gap-2 text-xs">
                        <span className="text-ink-faint">reads</span>
                        <input value={mappings[item.asset] ?? ""} placeholder="TABLE.COLUMN" aria-label={`source for ${item.asset}`}
                          onChange={(e) => setMappings({ ...mappings, [item.asset!]: e.target.value })}
                          className="w-72 rounded-md border border-line bg-pane px-2 py-1 font-mono" />
                        <span className="text-ink-faint">the CLI's --map</span>
                      </label>
                    ) : null}
                    {!atResolution && item.kind === "contract_owner" && item.asset ? (
                      <label className="mt-2 flex items-center gap-2 text-xs">
                        <span className="text-ink-faint">owner</span>
                        <input value={owners[item.asset] ?? ""} placeholder="Name <email>" aria-label={`owner for ${item.asset}`}
                          onChange={(e) => setOwners({ ...owners, [item.asset!]: e.target.value })}
                          className="w-72 rounded-md border border-line bg-pane px-2 py-1 font-mono" />
                        {(owners[item.asset] ?? "").trim() && !ownerValid(owners[item.asset] ?? "") ? (
                          <span className="text-bad">Name &lt;email&gt; or an email address</span>
                        ) : null}
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
