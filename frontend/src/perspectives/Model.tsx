import { useState } from "react";
import type { Construct, ModelView, SubjectArea } from "../types";
import { Mermaid } from "../components/Mermaid";
import { Empty, Pill, Section } from "../components/ui";

// WP80: the whole model, or one subject area — the schema of what each construct reads — with the
// hubs and links of other areas it reaches drawn dashed. A reading of the project, not a model field.
function AreaStrip({ areas, selected, onSelect }: { areas: SubjectArea[]; selected: string | null; onSelect: (name: string | null) => void }) {
  const button = (active: boolean) => `rounded-md border px-2 py-1 text-xs ${active ? "border-accent text-accent" : "border-line text-ink-dim hover:text-ink"}`;
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="text-ink-faint">subject areas</span>
      <button type="button" className={button(selected === null)} onClick={() => onSelect(null)}>whole model</button>
      {areas.map((a) => {
        const count = a.hubs.length + a.links.length + a.satellites.length;
        return (
          <button key={a.name} type="button" className={button(selected === a.name)} onClick={() => onSelect(a.name)}>
            <span className="font-mono">{a.name}</span> <span className="text-ink-faint">{count}</span>
            {a.increment ? <span className="ml-1 text-info">increment</span> : null}
          </button>
        );
      })}
    </div>
  );
}

export function ModelPerspective({ view, error }: { view: ModelView | null; error: string | null }) {
  const [selected, setSelected] = useState<Construct | null>(null);
  const [areaName, setAreaName] = useState<string | null>(null);
  if (error) return <Section title="Model"><Empty>{error}</Empty></Section>;
  if (!view) return <Section title="Model"><Empty>loading…</Empty></Section>;
  const m = view.model;
  const areas = view.areas ?? [];
  const area = areas.find((a) => a.name === areaName) ?? null;
  const existing = new Set<string>([...(view.existing?.hubs ?? []), ...(view.existing?.links ?? []), ...(view.existing?.satellites ?? [])].map((c) => c.name));
  const neighbours = new Set<string>(area?.neighbours ?? []);
  const shown = area ? new Set<string>([...area.hubs, ...area.links, ...area.satellites, ...area.neighbours]) : null;
  const whole: [string, Construct[]][] = [["hubs", m.hubs], ["links", m.links], ["satellites", m.satellites]];
  const inventory: [string, Construct[]][] = whole.map(([kind, constructs]) => [kind, shown ? constructs.filter((c) => shown.has(c.name)) : constructs]);
  const diagramTitle = area
    ? `Subject area ${area.name} — ${area.hubs.length} hubs, ${area.links.length} links, ${area.satellites.length} satellites${area.neighbours.length ? `, ${area.neighbours.length} neighbours dashed` : ""}`
    : "Output model — the raw vault (hubs, links, satellites)";
  return (
    <div className="grid gap-4">
      {areas.length > 1 ? <AreaStrip areas={areas} selected={areaName} onSelect={setAreaName} /> : null}
      <div className="grid gap-4 xl:grid-cols-2">
        <Mermaid title={diagramTitle} source={area ? area.mermaid : view.output_mermaid} />
        <Mermaid title="Input model — the declared source schema with its foreign keys" source={view.input_mermaid} />
      </div>
      <Section title={area ? `Inventory — ${area.name}` : "Inventory"} aside={<span className="flex gap-2">{inventory.map(([k, v]) => <Pill key={k}>{v.length} {k}</Pill>)}{view.existing ? <Pill tone="info">brownfield: {existing.size} existing</Pill> : null}</span>}>
        <div className="grid gap-4 md:grid-cols-3">
          {inventory.map(([kind, constructs]) => (
            <div key={kind}>
              <h3 className="mb-1 text-xs uppercase tracking-wide text-ink-faint">{kind}</h3>
              <ul className="divide-y divide-line text-sm">
                {constructs.length === 0 ? <li><Empty>none</Empty></li> : null}
                {constructs.map((c) => (
                  <li key={c.name}>
                    <button type="button" onClick={() => setSelected(c)} className={`flex w-full items-center justify-between py-1 text-left font-mono text-xs hover:text-accent ${selected?.name === c.name ? "text-accent" : ""}`}>
                      {c.name}
                      <span className="flex gap-1">
                        {neighbours.has(c.name) ? <Pill>neighbour</Pill> : null}
                        {existing.has(c.name) ? <Pill tone="info">existing</Pill> : null}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        {selected ? (
          <div className="mt-4 rounded-md border border-line bg-pane-2 p-3">
            <h3 className="mb-2 font-mono text-sm text-accent">{selected.name}</h3>
            <pre className="max-h-96 overflow-auto font-mono text-xs leading-5">{JSON.stringify(selected, null, 2)}</pre>
          </div>
        ) : <p className="mt-3 text-xs text-ink-faint">select a construct for its definition as the model carries it</p>}
      </Section>
    </div>
  );
}
