import { useMemo, useState } from "react";
import type { Checkpoint, Decision, KeyAnswer, LinkDecision, ResolutionDecision, ReviewItem, Run, StageBinding } from "../types";
import { Button, Choice, Empty, ErrorNote, Pill, Section } from "../components/ui";

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
  const [bridges, setBridges] = useState<Record<string, boolean>>({}); // WP115: --bridge / --no-bridge
  const [bridgePaths, setBridgePaths] = useState<Record<string, string>>({}); // WP144: the path of a built group
  // WP126 (ADR-0021): the chosen key per contested table and the reason a technical key needs.
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [keyReasons, setKeyReasons] = useState<Record<string, string>>({});
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
  // WP140 (C74): an inferred key is declined by the bulk answer unless a human names it (ADR-0018 §4,
  // `apply_link_decision`) — so it is shown unchecked, apart from the declared ones, and a check is the yes.
  const allLinks = atResolution ? checkpoint.links : [];
  const declaredLinks = allLinks.filter((l) => l.provenance !== "inferred");
  const inferredLinks = allLinks.filter((l) => l.provenance === "inferred");
  const declined = declaredLinks.filter((l) => links[l.key] === false).length;
  const allowedInferred = inferredLinks.filter((l) => links[l.key] === true).length;
  const changes = [declined ? `decline ${declined}` : null, allowedInferred ? `allow ${allowedInferred} inferred` : null].filter(Boolean);
  // WP142 (C51): the proposal in words, and the hubs a resolution may name instead of it. The
  // proposal's own hub is no "other" answer; a same-as proposal's candidate is (a merge onto it).
  const keptAs = (p: ResolutionDecision): string =>
    p.proposed === undefined ? `proposed ${p.claim}`
      : p.proposed === "same_as_candidate" ? `same as ${p.same_as ?? "its candidate"}, keyed differently`
        : `is ${p.proposed}`;
  const otherHubs = (p: ResolutionDecision): string[] => (checkpoint.hubs ?? []).filter((h) => h !== p.proposed);
  const pendingBindings = atResolution ? [] : (checkpoint.bindings ?? []);
  const pendingBridges = atResolution ? [] : (checkpoint.bridges ?? []);
  const pendingKeys = atResolution ? (checkpoint.keys ?? []) : [];
  const joined = (columns: string[]): string => columns.join("+");
  const chosenKey = (k: { table: string; default: string[] }): string => keys[k.table] ?? joined(k.default);
  // The technical primary key is the one answer that needs a reason — as `--key-reason` does.
  const needsReason = (k: { table: string; default: string[]; primary_key: string[] }): boolean =>
    chosenKey(k) === joined(k.primary_key) && chosenKey(k) !== joined(k.default);
  const keysAnswerable = pendingKeys.every((k) => !needsReason(k) || (keyReasons[k.table] ?? "").trim() !== "");
  // Only a named answer is sent; a key left at its default takes the declared natural key anyway.
  const keyAnswers = (): Record<string, KeyAnswer> => {
    const out: Record<string, KeyAnswer> = {};
    for (const k of pendingKeys) {
      const choice = chosenKey(k);
      if (choice === joined(k.default)) continue;
      const reason = (keyReasons[k.table] ?? "").trim();
      out[k.table] = { columns: choice.split("+"), reason: needsReason(k) ? reason : null };
    }
    return out;
  };
  // WP144 (C53 a): one decision per group — the link pair and the hub they share; its paths differ
  // in their ends. `bridges` holds the answer per group, `bridgePaths` the path chosen for a built one.
  const bridgeGroups = (() => { // computed per render: this sits below the early returns, where a hook may not
    const groups = new Map<string, { key: string; links: string[]; hub: string | null; paths: string[]; requirement_ids: string[]; evidence: string[] }>();
    for (const b of pendingBridges) {
      const key = b.group ?? b.path;
      const g = groups.get(key) ?? { key, links: b.links ?? [], hub: b.hub ?? null, paths: [], requirement_ids: [], evidence: b.evidence };
      g.paths.push(b.path);
      for (const r of b.requirement_ids) if (!g.requirement_ids.includes(r)) g.requirement_ids.push(r);
      groups.set(key, g);
    }
    return [...groups.values()];
  })();
  const chosenPath = (g: { key: string; paths: string[] }): string => {
    const picked = bridgePaths[g.key];
    return picked !== undefined && g.paths.includes(picked) ? picked : g.paths[0]!;
  };
  // Every path is answered: the chosen path of a group set to build is the yes, everything else is
  // declined — a bridge is never built by default.
  const bridgeAnswers = (): Record<string, boolean> =>
    Object.fromEntries(bridgeGroups.flatMap((g) => g.paths.map((p) => [p, bridges[g.key] === true && p === chosenPath(g)])));
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
    bridges: atResolution ? {} : bridgeAnswers(),
    keys: atResolution ? keyAnswers() : {},
  });

  // WP142 (C52): two named answers, the default first — a licence allows, everything else builds.
  const NO = { value: "no", label: "Decline" } as const;
  const yes = (l: LinkDecision) => ({ value: "yes", label: l.kind === "license" ? "Allow" : "Build" } as const);
  const linkRow = (l: LinkDecision, build: boolean) => (
    <li key={l.key} className="rounded-md border border-line bg-pane-2 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <code className="font-mono text-xs text-accent">{l.key}</code>
        <span>→ {l.target}</span>
        <Pill>{l.kind}</Pill>
        <Choice label={`decision for ${l.key}`} value={build ? "yes" : "no"}
          onChange={(v) => setLinks({ ...links, [l.key]: v === "yes" })}
          options={l.provenance === "inferred" ? [NO, yes(l)] : [yes(l), NO]} />
      </div>
      <p className="mt-1 text-xs text-ink-dim">{l.note}</p>
      {l.evidence.map((e, i) => <p key={i} className="text-xs text-ink-faint">{e}</p>)}
    </li>
  );

  return (
    <div className="grid gap-4">
      <Section title={atResolution ? "Resolution checkpoint — before the modeler" : "Sign-off checkpoint"}
        aside={<span className="flex gap-2">
          {atResolution ? <><Pill tone="warn">{checkpoint.links.length} proposals</Pill><Pill tone="warn">{checkpoint.resolutions.length} resolutions</Pill>{pendingKeys.length ? <Pill tone="warn">{pendingKeys.length} hub keys</Pill> : null}</>
            : <><Pill tone="warn">{checkpoint.decisions} decisions</Pill><Pill>{checkpoint.disclosures} disclosures</Pill>{checkpoint.blocked ? <Pill tone="bad">blocked</Pill> : <Pill tone="ok">not blocked</Pill>}</>}
        </span>}>
        <p className="text-sm text-ink-dim">
          {atResolution
            ? `The run paused before the model is built: declared keys, entity resolutions and contested hub keys need a decision that steers the modeler. Everything left as proposed is ratified by accept — the CLI's --accept; a contested hub key then takes the declared natural key.${inferredLinks.length ? " An inferred key is the exception: it is declined unless allowed below." : ""} Owners and the model's review come at sign-off, after the modeler.`
            : checkpoint.blocked ? "Something blocks agreement — a validation error or a contract without an owner. Answer the decisions, then accept, or discard the run." : "Nothing blocks agreement. Review the decisions and accept, or discard."}
        </p>
        <ErrorNote error={error} />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={() => onDecide(decision(true))} disabled={busy || (!atResolution && checkpoint.blocked && !ownersFilled) || !keysAnswerable} title={!keysAnswerable ? "a hub on its technical primary key needs a reason" : !atResolution && checkpoint.blocked && !ownersFilled ? "every contract needs an owner: 'Name <email>' or an email address" : undefined}>
            {atResolution ? (changes.length ? `Ratify the rest, ${changes.join(", ")}, and build the model` : "Ratify as proposed and build the model") : "Accept and continue"}
          </Button>
          {!atResolution ? <Button kind="add" onClick={() => onDecide(decision(false))} disabled={busy} title={checkpoint.blocked ? "record owners and resolutions without accepting; the run stays paused" : "record owners and resolutions without accepting — nothing blocks, so the run finishes"}>Record without accepting</Button> : null}
          <Button kind="danger" onClick={() => onDecide({ discard: true })} disabled={busy}>Discard the run</Button>
        </div>
      </Section>

      {declaredLinks.length > 0 ? (
        <Section title="Declared keys — links, relationship tables and key licenses">
          <p className="mb-2 text-xs text-ink-faint">Proposed from the source's own foreign keys. Build (for a license: allow) is the default, as in the CLI's prompt (`--link`); decline is the exception (`--no-link`). A license builds nothing: it allows the translation or alias the modeler will need.</p>
          <ul className="grid gap-2 text-sm">{declaredLinks.map((l) => linkRow(l, links[l.key] !== false))}</ul>
        </Section>
      ) : null}

      {inferredLinks.length > 0 ? (
        <Section title="Inferred keys — found in the data, declared nowhere" aside={<Pill tone="warn">{inferredLinks.length} inferred</Pill>}>
          <p className="mb-2 text-xs text-ink-dim">`vault-agent infer-keys` found that every value of the column occurs in the key it names. That is evidence, not a declaration — it can hold by coincidence. <strong>Declined unless you allow it</strong>, as the CLI's `--accept` declines it; allowed, it is the CLI's `--link`: the link built on it is bound and its key translated like a declared one, and the translation is flagged to confirm at sign-off.</p>
          <ul className="grid gap-2 text-sm">{inferredLinks.map((l) => linkRow(l, links[l.key] === true))}</ul>
        </Section>
      ) : null}

      {pendingKeys.length > 0 ? (
        <Section title="Hub keys — a technical primary key against a declared natural key">
          <p className="mb-2 text-xs text-ink-faint">Each table declares a natural key the requirements did not name first. Left as shown, the hub is keyed on the natural key — the CLI's default. Keying a hub on its technical primary key needs a reason, which goes into the proposed ADR (`--key`, `--key-reason`); a composite key is answered in the terminal.</p>
          <ul className="grid gap-2 text-sm">
            {pendingKeys.map((k) => {
              const options = [...k.natural_keys.filter((c) => c !== joined(k.default)), joined(k.primary_key)];
              return (
                <li key={k.table} className="rounded-md border border-line bg-pane-2 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <code className="font-mono text-xs text-accent">{k.table}</code>
                    <span>→ hub key</span>
                    <select value={chosenKey(k)} aria-label={`hub key for ${k.table}`}
                      onChange={(e) => setKeys({ ...keys, [k.table]: e.target.value })}
                      className="rounded-md border border-line bg-pane px-2 py-1 font-mono text-xs">
                      <option value={joined(k.default)}>{joined(k.default)} — the declared natural key</option>
                      {options.map((c) => <option key={c} value={c}>{c}{c === joined(k.primary_key) ? " — the technical primary key" : ""}</option>)}
                    </select>
                    {needsReason(k) ? (
                      <label className="grid gap-1 text-xs">
                        <input value={keyReasons[k.table] ?? ""} placeholder="why the technical key"
                          aria-label={`reason for ${k.table}`}
                          onChange={(e) => setKeyReasons({ ...keyReasons, [k.table]: e.target.value })}
                          className="w-72 rounded-md border border-line bg-pane px-2 py-1 text-xs" />
                        {(keyReasons[k.table] ?? "").trim() === "" ? <span className="text-bad">a reason is required for the technical key</span> : null}
                      </label>
                    ) : null}
                  </div>
                  {k.evidence.map((e, i) => <p key={i} className="text-xs text-ink-faint">{e}</p>)}
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
                  <select value={resolutions[p.concept] ?? ""} aria-label={`resolution for ${p.concept}`}
                    onChange={(e) => setResolutions({ ...resolutions, [p.concept]: e.target.value })}
                    className="w-80 rounded-md border border-line bg-pane px-2 py-1 text-xs">
                    <option value="">Keep the proposal — {keptAs(p)}</option>
                    <option value="NEW">New hub</option>
                    <option value="unresolved">Leave unresolved</option>
                    {otherHubs(p).length ? <optgroup label="Another existing hub">{otherHubs(p).map((h) => <option key={h} value={h}>{h}</option>)}</optgroup> : null}
                  </select>
                </div>
                {p.evidence.map((e, i) => <p key={i} className="text-xs text-ink-faint">{e}</p>)}
              </li>
            ))}
          </ul>
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

      {bridgeGroups.length > 0 ? (
        <Section title="Bridges — proposed from the requirements, built only when you say so">
          <p className="text-xs text-ink-dim">Each entry joins two links that cite the same requirement around a shared hub — one decision per link pair. A bridge is Business Vault logic (ADR-0007): left at decline every path of it is declined, as the CLI's <code className="font-mono">--accept</code> declines an unanswered one; set to build, the path shown is built — <code className="font-mono">--bridge</code>. Where a pair can be walked between several ends, choose the path; a second path of the same pair is the CLI's.</p>
          <ul className="mt-2 grid gap-2 text-sm">
            {bridgeGroups.map((g) => {
              const build = bridges[g.key] === true;
              const chosen = chosenPath(g);
              return (
                <li key={g.key} className="rounded-md border border-line bg-pane-2 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    {g.links.length === 2
                      ? <span><code className="font-mono text-xs text-accent">{g.links[0]}</code> and <code className="font-mono text-xs text-accent">{g.links[1]}</code> through <code className="font-mono text-xs">{g.hub}</code></span>
                      : <code className="font-mono text-xs text-accent">{g.key}</code>}
                    {g.requirement_ids.map((r) => <Pill key={r}>{r}</Pill>)}
                    {g.paths.length > 1 ? <Pill>{g.paths.length} paths</Pill> : null}
                    <Choice label={`decision for bridge ${g.key}`} value={build ? "yes" : "no"}
                      onChange={(v) => setBridges({ ...bridges, [g.key]: v === "yes" })}
                      options={[NO, { value: "yes", label: "Build" }]} />
                  </div>
                  {build && g.paths.length > 1 ? (
                    <label className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                      <span className="text-ink-faint">along</span>
                      <select value={chosen} aria-label={`path for ${g.key}`}
                        onChange={(e) => setBridgePaths({ ...bridgePaths, [g.key]: e.target.value })}
                        className="max-w-full rounded-md border border-line bg-pane px-2 py-1 font-mono text-xs">
                        {g.paths.map((p) => <option key={p} value={p}>{p}</option>)}
                      </select>
                    </label>
                  ) : <p className="mt-1 font-mono text-xs text-ink-dim">{g.paths.length > 1 ? `${g.paths[0]} — and ${g.paths.length - 1} more with other ends` : g.paths[0]}</p>}
                  {g.evidence.map((e, i) => <p key={i} className="mt-1 text-xs text-ink-faint">{e}</p>)}
                </li>
              );
            })}
          </ul>
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
