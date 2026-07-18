"""WP11 — static, self-contained HTML run report (UI-track stage 1).

A single ``report.html`` per run that a human (or a prospect in a demo) can *open and
see*: the Data Vault model as a graph, the validation verdict, what needs sign-off, the
proposed source mappings, and the contracts. Emitted by :func:`cli.write_outputs`; no
server, no state, analogous in spirit to dbt docs.

Deterministic and presentation-only (peer of
:func:`agents.orchestrator.render_review_queue_md`) — no LLM, no agent, no business logic:

* **Byte-identical for identical state.** No timestamps, no environment info — the report is
  a pure function of the state (the WP2 ADR determinism property).
* **Every state string is treated as hostile.** All LLM-derived text passes through
  :func:`html.escape` (and, in Mermaid labels, the same escaping so a hostile name can never
  break the label delimiter or inject a raw ``<script>``). The only raw ``<script>`` in the
  document is the single pinned Mermaid CDN include.
* **The review queue is rendered through the WP5 §5.1 presentation API** — this module is the
  *third* renderer (after ``render_review_queue_md`` and the CLI checkpoint); it imports
  ``KIND_HEADINGS``/``KIND_ORDER``/``aggregate_review_flags`` and never duplicates that
  knowledge.

The DV model is a graph, so it is shown as one: a Mermaid ``flowchart`` whose *source text* is
generated here (pure Python) and laid out by the browser. On CDN-load failure the report stays
fully readable — the source is always present in a ``<details>`` block that an ``onerror``
handler un-collapses.
"""
import html

from vault_agent.agents.orchestrator import (
    KIND_HEADINGS,
    KIND_ORDER,
    aggregate_review_flags,
    assemble_review_queue,
)
from vault_agent.models.contract import ContractOwner
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import DVModel, VaultAgentState

# Pinned major version; the browser UMD build (verified present on jsdelivr for v11:
# dist/mermaid.min.js). Init/fallback run via the tag's own onload/onerror attributes so the
# document carries exactly one <script> — the single allowed raw include.
_MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"

# Mermaid node class per satellite type (the graph's visual DV vocabulary).
_SAT_CLASS = {
    "standard": "sat_standard",
    "multi_active": "sat_multi_active",
    "effectivity": "sat_effectivity",
}


def _esc(value: object) -> str:
    """Escape an untrusted (LLM-derived) string for any HTML text/attribute context."""
    return html.escape(str(value))


def _node_id(name: str) -> str:
    """A safe Mermaid node id from a construct name (single normalisation source of truth).

    ``normalize_identifier`` yields UPPER_SNAKE; two constructs normalising identically is a
    validator concern (E_DUP_HUB etc.), not the report's — last-write-wins is fine here."""
    return normalize_identifier(name) or "NODE"


def _mlabel(*parts: str) -> str:
    """Build a Mermaid label from raw parts, escaping each so it is safe as label text.

    Each dynamic part is HTML-escaped (``<`` → ``&lt;``, ``"`` → ``&quot;``), which both keeps
    the surrounding ``["..."]`` delimiter intact and guarantees no raw ``<script>`` reaches the
    label. Callers interleave the literal ``<br/>`` separator between parts for line breaks
    (Mermaid renders it; the browser un-escapes the embedded source back to it)."""
    return "".join(_esc(part) for part in parts)


def build_model_mermaid(model: DVModel) -> str:
    """Render the DV model as Mermaid ``flowchart LR`` source (pure string generation).

    Hubs are rectangles, links hexagons, satellites rounded rectangles (one class per
    ``sat_type``). A multi-source hub (``Hub.sources``) gets one cylinder per feed with an edge
    into the hub. Link participations are read through ``Link.hub_refs`` (never raw
    ``connected_hubs``); a role-qualified ref carries its role as the edge label, and a
    driving-key participation (``Link.resolve_driving_refs()``) renders as a thick ``==>`` edge.
    A satellite with its own ``source_table`` (WP7 §7.1) notes it in the label. Emission order
    is deterministic: hubs, links, satellites, each in model-list order."""
    lines = ["flowchart LR"]
    # Static, deterministic styling for the construct classes.
    lines += [
        "  classDef hub fill:#dbeafe,stroke:#1e40af,color:#0b1324;",
        "  classDef hubsource fill:#eff6ff,stroke:#93c5fd,color:#0b1324;",
        "  classDef link fill:#dcfce7,stroke:#166534,color:#0b1324;",
        "  classDef sat_standard fill:#fef9c3,stroke:#a16207,color:#0b1324;",
        "  classDef sat_multi_active fill:#fed7aa,stroke:#c2410c,color:#0b1324;",
        "  classDef sat_effectivity fill:#e9d5ff,stroke:#7e22ce,color:#0b1324;",
    ]

    for hub in model.hubs:
        hid = _node_id(hub.name)
        lines.append(f'  {hid}["{_mlabel(hub.name)}<br/>BK: {_mlabel(hub.business_key)}"]')
        lines.append(f"  class {hid} hub;")
        for index, source in enumerate(hub.sources):
            sid = f"{hid}__SRC{index}"
            label = _mlabel(f"{source.source_table}.{source.business_key_column}")
            lines.append(f'  {sid}[("{label}")]')
            lines.append(f"  class {sid} hubsource;")
            lines.append(f"  {sid} --> {hid}")

    for link in model.links:
        lid = _node_id(link.name)
        label = _mlabel(link.name)
        if link.link_type == "transactional":
            label += "<br/>(transactional)"
        lines.append(f'  {lid}{{{{"{label}"}}}}')
        lines.append(f"  class {lid} link;")
        driving = {(ref.hub, ref.role) for ref in link.resolve_driving_refs()}
        for ref in link.hub_refs:
            arrow = "==>" if (ref.hub, ref.role) in driving else "-->"
            target = _node_id(ref.hub)
            if ref.role:
                lines.append(f'  {lid} {arrow}|"{_mlabel(ref.role)}"| {target}')
            else:
                lines.append(f"  {lid} {arrow} {target}")

    for sat in model.satellites:
        sid = _node_id(sat.name)
        label = _mlabel(sat.name)
        if sat.source_table:
            label += f"<br/>src: {_mlabel(sat.source_table)}"
        lines.append(f'  {sid}("{label}")')
        lines.append(f"  class {sid} {_SAT_CLASS.get(sat.sat_type, 'sat_standard')};")
        lines.append(f"  {_node_id(sat.parent)} --- {sid}")

    return "\n".join(lines)


def _badge(text: str, kind: str) -> str:
    return f'<span class="badge {kind}">{_esc(text)}</span>'


def _table(headers: list[str], rows: list[list[str]]) -> str:
    """A simple HTML table; header cells are static, body cells are pre-escaped by the caller."""
    head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _header_section(state: VaultAgentState) -> str:
    model = state.dv_model
    report = state.validation_report
    queue = assemble_review_queue(state)
    grounding = "unknown" if state.plan is None else ("on" if state.plan.grounded else "off")

    verdict = (
        _badge("validation passed", "ok")
        if report.passed
        else _badge("validation failed", "err")
    )
    signoff = (
        _badge("requires sign-off", "err")
        if queue.requires_signoff
        else _badge("no sign-off needed", "ok")
    )
    counts = [
        f"{len(model.hubs)} hubs",
        f"{len(model.links)} links",
        f"{len(model.satellites)} satellites",
        f"{len(state.artifacts.dbt_models)} raw-vault models",
        f"{len(state.artifacts.staging_models)} staging models",
        f"{len(state.artifacts.contracts)} contracts",
        f"{len(state.adrs)} ADRs",
    ]
    chips = "".join(f'<span class="chip">{_esc(c)}</span>' for c in counts)
    return (
        "<header>"
        "<h1>Vault-Agent run report</h1>"
        f"<div class='badges'>{verdict}{signoff}"
        f"<span class='badge muted'>grounding: {_esc(grounding)}</span></div>"
        f"<div class='chips'>{chips}</div>"
        "</header>"
    )


def _graph_section(model: DVModel) -> str:
    if not (model.hubs or model.links or model.satellites):
        return ""
    source = build_model_mermaid(model)
    escaped = _esc(source)  # embedded twice: the browser un-escapes each back to the source
    return (
        "<section><h2>Model graph</h2>"
        f'<pre class="mermaid">{escaped}</pre>'
        '<details class="graph-source"><summary>Graph source '
        "(renders on GitHub / mermaid.live if the diagram did not load)</summary>"
        f"<pre>{escaped}</pre></details>"
        "</section>"
    )


def _inventory_section(model: DVModel) -> str:
    if not (model.hubs or model.links or model.satellites):
        return "<section><h2>Constructs</h2><p>No model constructs were generated.</p></section>"

    blocks: list[str] = ["<section><h2>Constructs</h2>"]
    if model.hubs:
        rows = [
            [
                _esc(hub.name),
                _esc(hub.business_key),
                _esc(hub.source_entity),
                _esc(", ".join(f"{s.source_table}.{s.business_key_column}" for s in hub.sources))
                or "—",
                _esc(hub.description),
            ]
            for hub in model.hubs
        ]
        blocks.append("<h3>Hubs</h3>")
        blocks.append(
            _table(["Hub", "Business key", "Source entity", "Sources", "Description"], rows)
        )
    if model.links:
        rows = []
        for link in model.links:
            parts = ", ".join(
                (ref.hub if ref.role is None else f"{ref.hub} ({ref.role})")
                for ref in link.hub_refs
            )
            driving = ", ".join(str(ref) for ref in link.resolve_driving_refs()) or "—"
            rows.append(
                [
                    _esc(link.name),
                    _esc(link.link_type),
                    _esc(parts),
                    _esc(driving),
                    _esc(link.unit_of_work or "—"),
                    _esc(len(link.payload)),
                ]
            )
        blocks.append("<h3>Links</h3>")
        blocks.append(
            _table(
                ["Link", "Type", "Participations", "Driving key", "Unit of work", "Payload"],
                rows,
            )
        )
    if model.satellites:
        rows = [
            [
                _esc(sat.name),
                _esc(sat.sat_type),
                _esc(sat.parent),
                _esc(len(sat.attributes)),
                _esc(", ".join(sat.child_dependent_key) or "—"),
                _esc(sat.source_table or "—"),
                _esc(sat.split_rationale or "—"),
            ]
            for sat in model.satellites
        ]
        blocks.append("<h3>Satellites</h3>")
        blocks.append(
            _table(
                ["Satellite", "Type", "Parent", "Attrs", "CDK", "Source table", "Split rationale"],
                rows,
            )
        )
    blocks.append("</section>")
    return "".join(blocks)


def _validation_section(state: VaultAgentState) -> str:
    report = state.validation_report
    verdict = "PASSED" if report.passed else "FAILED"
    head = f"<section><h2>Validation — {verdict}</h2>"
    if not report.issues:
        return head + "<p>No validation issues.</p></section>"
    rows = [
        [_esc(issue.severity), _esc(issue.code), _esc(issue.construct), _esc(issue.message)]
        for issue in report.issues
    ]
    return head + _table(["Severity", "Code", "Construct", "Message"], rows) + "</section>"


def _review_section(state: VaultAgentState) -> str:
    """Third renderer over the WP5 §5.1 review-queue presentation API (no duplicated knowledge)."""
    queue = assemble_review_queue(state)
    head = "<section><h2>Review queue</h2>"
    if not queue.items:
        return head + "<p>No items require human review. ✅</p></section>"
    verdict = "requires sign-off" if queue.requires_signoff else "advisory only"
    status = f"<p><strong>Status:</strong> {_esc(verdict)} — {len(queue.items)} item(s).</p>"
    blocks = [head, status]
    grouped = queue.by_kind()
    for kind in KIND_ORDER:
        group = grouped.get(kind)
        if not group:
            continue
        if kind == "review_flag":
            group = aggregate_review_flags(group)
        blocks.append(f"<h3>{_esc(KIND_HEADINGS[kind])}</h3><ul>")
        for item in group:
            line = f"<strong>{_esc(item.summary)}</strong>"
            if item.detail:
                line += f" — {_esc(item.detail)}"
            if item.source:
                line += f" <em>({_esc(item.source)})</em>"
            blocks.append(f"<li>{line}</li>")
        blocks.append("</ul>")
    blocks.append("</section>")
    return "".join(blocks)


def _mappings_section(state: VaultAgentState) -> str:
    mapping = state.mappings
    if not (mapping.proposals or mapping.gaps or mapping.unresolved):
        return ""
    blocks = ["<section><h2>Source mappings</h2>"]
    if mapping.proposals:
        rows = [
            [
                _esc(p.concept),
                _esc(f"{p.table}.{p.column}"),
                _esc(p.category),
                _esc(f"{p.confidence:.3f}"),
                _esc(p.ratification_status),
            ]
            for p in mapping.proposals
        ]
        blocks.append(
            _table(["Concept", "Source", "Category", "Confidence", "Status"], rows)
        )
    if mapping.gaps:
        items = "".join(f"<li>{_esc(g)}</li>" for g in mapping.gaps)
        blocks.append(f"<h3>Coverage gaps (no in-scope source)</h3><ul>{items}</ul>")
    if mapping.unresolved:
        items = "".join(f"<li>{_esc(u)}</li>" for u in mapping.unresolved)
        blocks.append(f"<h3>Unresolved (need a decision)</h3><ul>{items}</ul>")
    blocks.append(
        "<p class='hint'>Ratify in <code>mappings.review.yml</code> "
        "(<code>vault-agent resume --mappings &lt;file&gt;</code>).</p></section>"
    )
    return "".join(blocks)


def _contracts_section(state: VaultAgentState) -> str:
    contracts = state.artifacts.contracts
    if not contracts:
        return ""
    rows = []
    for contract in contracts:
        owner = contract.get("owner") or {}
        if owner.get("name") == ContractOwner.PLACEHOLDER_NAME:
            owner_cell = "⚠ unassigned"
        else:
            name = str(owner.get("name", "—"))
            email = owner.get("email")
            owner_cell = _esc(f"{name} <{email}>" if email else name)
        fields = contract.get("schema") or []
        rows.append(
            [_esc(contract.get("name", "—")), owner_cell, _esc(len(fields))]
        )
    return (
        "<section><h2>Data contracts</h2>"
        + _table(["Contract", "Owner", "Fields"], rows)
        + "</section>"
    )


def _files_section(state: VaultAgentState) -> str:
    """A collapsed list of the paths write_outputs writes (a convenience map, not a manifest)."""
    paths: list[str] = []
    paths += [f"models/raw_vault/{name}.sql" for name in state.artifacts.dbt_models]
    paths += [f"models/staging/{name}.sql" for name in state.artifacts.staging_models]
    paths += list(state.artifacts.scaffolding)
    for contract in state.artifacts.contracts:
        asset = str(contract.get("name", "contract"))
        paths.append(f"contracts/{asset}.contract.yml")
    if state.adrs:
        paths.append(f"adrs/ ({len(state.adrs)} ADR file(s))")
    if not paths:
        return ""
    items = "".join(f"<li><code>{_esc(p)}</code></li>" for p in paths)
    return (
        "<section><details><summary>Generated files</summary>"
        f"<ul class='files'>{items}</ul></details></section>"
    )


_STYLE = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; padding: 2rem; color: #0b1324; background: #f8fafc;
  font: 15px/1.55 -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; }
main { max-width: 1100px; margin: 0 auto; }
header h1 { margin: 0 0 .5rem; font-size: 1.6rem; }
h2 { margin-top: 2rem; border-bottom: 2px solid #e2e8f0; padding-bottom: .3rem; }
h3 { margin: 1.2rem 0 .4rem; font-size: 1rem; color: #334155; }
.badges { margin: .3rem 0 .6rem; }
.badge { display: inline-block; padding: .15rem .55rem; border-radius: 999px;
  font-size: .8rem; font-weight: 600; margin-right: .4rem; }
.badge.ok { background: #dcfce7; color: #166534; }
.badge.err { background: #fee2e2; color: #991b1b; }
.badge.muted { background: #e2e8f0; color: #334155; }
.chips .chip { display: inline-block; background: #eef2ff; color: #3730a3;
  border-radius: 6px; padding: .1rem .5rem; margin: .15rem .3rem .15rem 0; font-size: .82rem; }
table { border-collapse: collapse; width: 100%; margin: .4rem 0 1rem; font-size: .88rem; }
th, td { border: 1px solid #e2e8f0; padding: .35rem .55rem; text-align: left; vertical-align: top; }
th { background: #f1f5f9; }
tr:nth-child(even) td { background: #fafcff; }
ul { margin: .3rem 0 1rem; }
code { background: #f1f5f9; padding: .05rem .3rem; border-radius: 4px; font-size: .85em; }
pre.mermaid { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 1rem; overflow-x: auto; }
details { margin: .6rem 0; }
summary { cursor: pointer; font-weight: 600; color: #334155; }
.hint { color: #475569; font-size: .85rem; }
.files { columns: 2; font-size: .82rem; }
"""


def build_report(state: VaultAgentState) -> str:
    """Build the complete, self-contained HTML run report for ``state`` (deterministic)."""
    sections = [
        _header_section(state),
        _graph_section(state.dv_model),
        _inventory_section(state.dv_model),
        _validation_section(state),
        _review_section(state),
        _mappings_section(state),
        _contracts_section(state),
        _files_section(state),
    ]
    body = "".join(section for section in sections if section)
    # Single <script>: the pinned Mermaid include. Its own onload initialises + runs Mermaid;
    # its onerror (and the missing-global path) un-collapses the graph-source <details> so the
    # report is fully readable with the CDN blocked. securityLevel 'strict' sanitises labels.
    script = (
        f'<script src="{_MERMAID_CDN}" '
        "onload=\"mermaid.initialize({securityLevel:'strict'}); mermaid.run();\" "
        "onerror=\"document.querySelectorAll('details.graph-source').forEach("
        "function(d){d.open=true;});\"></script>"
    )
    return (
        "<!doctype html>"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Vault-Agent run report</title>"
        f"<style>{_STYLE}</style></head>"
        f"<body><main>{body}</main>{script}</body></html>"
    )
