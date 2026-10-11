import { useState } from "react";
import type { Construct, ModelView } from "../types";
import { Mermaid } from "../components/Mermaid";
import { Empty, Pill, Section } from "../components/ui";

export function ModelPerspective({ view, error }: { view: ModelView | null; error: string | null }) {
  const [selected, setSelected] = useState<Construct | null>(null);
  if (error) return <Section title="Model"><Empty>{error}</Empty></Section>;
  if (!view) return <Section title="Model"><Empty>loading…</Empty></Section>;
  const m = view.model;
  const existing = new Set<string>([...(view.existing?.hubs ?? []), ...(view.existing?.links ?? []), ...(view.existing?.satellites ?? [])].map((c) => c.name));
  const inventory: [string, Construct[]][] = [["hubs", m.hubs], ["links", m.links], ["satellites", m.satellites]];
  return (
    <div className="grid gap-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <Mermaid title="Output model — the raw vault (hubs, links, satellites)" source={view.output_mermaid} />
        <Mermaid title="Input model — the declared source schema with its foreign keys" source={view.input_mermaid} />
      </div>
      <Section title="Inventory" aside={<span className="flex gap-2">{inventory.map(([k, v]) => <Pill key={k}>{v.length} {k}</Pill>)}{view.existing ? <Pill tone="info">brownfield: {existing.size} existing</Pill> : null}</span>}>
        <div className="grid gap-4 md:grid-cols-3">
          {inventory.map(([kind, constructs]) => (
            <div key={kind}>
              <h3 className="mb-1 text-xs uppercase tracking-wide text-ink-faint">{kind}</h3>
              <ul className="divide-y divide-line text-sm">
                {constructs.length === 0 ? <li><Empty>none</Empty></li> : null}
                {constructs.map((c) => (
                  <li key={c.name}>
                    <button type="button" onClick={() => setSelected(c)} className={`flex w-full items-center justify-between py-1 text-left font-mono text-xs hover:text-accent ${selected?.name === c.name ? "text-accent" : ""}`}>
                      {c.name}{existing.has(c.name) ? <Pill tone="info">existing</Pill> : null}
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
