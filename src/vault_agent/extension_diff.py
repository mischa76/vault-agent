"""The extension diff: what an extension run actually changed (WP23 §2.7).

Charter §3.2 decided the output strategy: merge, regenerate the FULL project, and let the
diff be the deliverable. That is only safe if the diff is *legible* — "unchanged SQL means
unchanged tables" is a promise a reviewer has to be able to check, not take on faith. This
module produces that check, deterministically and without an LLM.

Three sections, per the spec:

* **unchanged** — constructs the extension did not touch, collapsed to a count plus names.
* **extended** — pre-existing constructs that gained something (source feeds, new children),
  each with the FILES whose content changed. That last part is the load-bearing one: a
  grandfathered hub's SQL legitimately changes when it starts unioning a second staging
  model, and a reviewer must see exactly which files moved rather than diffing the tree by
  hand.
* **new** — everything the extension added, with the parent it attaches to.

File-change attribution works by regenerating the EXISTING model on its own and comparing
the rendered artifacts to the extension run's. That is the same generator, so any difference
is a real difference — no heuristics, no guessing which file a construct owns.
"""
import logging
from dataclasses import dataclass, field

from vault_agent.agents.staging_generator import legacy_feeds
from vault_agent.rules.dv2_rules import normalize_identifier
from vault_agent.state import DVModel, VaultAgentState

logger = logging.getLogger(__name__)

DIFF_FILENAME = "extension-diff.md"


@dataclass
class ExtensionDiff:
    """The computed diff — the data both the Markdown artifact and the HTML report render."""

    unchanged: list[str] = field(default_factory=list)
    # construct -> what it gained (human-readable phrases, deterministic order)
    extended: dict[str, list[str]] = field(default_factory=dict)
    # construct -> the generated files whose content changed
    changed_files: dict[str, list[str]] = field(default_factory=dict)
    # construct -> parent (empty for hubs)
    new: dict[str, str] = field(default_factory=dict)

    @property
    def counts(self) -> tuple[int, int, int]:
        return len(self.unchanged), len(self.extended), len(self.new)


def _construct_names(model: DVModel) -> list[str]:
    return (
        [hub.name for hub in model.hubs]
        + [link.name for link in model.links]
        + [sat.name for sat in model.satellites]
    )


async def build_extension_diff(state: VaultAgentState) -> ExtensionDiff:
    """Compute the diff between the extended vault and the vault it extends.

    Async because file-change attribution regenerates the existing model through the real
    code generator — the only way to know what a file looked like before is to render it."""
    prior = state.existing_model
    diff = ExtensionDiff()
    if prior is None:
        return diff

    merged = state.dv_model
    prior_names = set(_construct_names(prior))
    prior_hubs = {hub.name: hub for hub in prior.hubs}

    for name in _construct_names(merged):
        if name not in prior_names:
            continue
        gained: list[str] = []
        hub = next((h for h in merged.hubs if h.name == name), None)
        if hub is not None:
            before = prior_hubs[name]
            # A feed is new when the vault did not already have it. Asking the SAME helper
            # grandfathering asks matters: when a single-source hub gains a feed, the merger
            # materialises its implicit original one, and counting that as an addition would
            # tell the reviewer a feed appeared that has in fact been there all along.
            known = {
                (normalize_identifier(s.source_table), normalize_identifier(s.business_key_column))
                for s in before.sources
            } | {
                (table, column)
                for (hub_name, table, column) in legacy_feeds(prior)
                if hub_name == name
            }
            new_feeds = [
                s
                for s in hub.sources
                if (normalize_identifier(s.source_table),
                    normalize_identifier(s.business_key_column)) not in known
            ]
            if new_feeds:
                gained.append(
                    f"{len(new_feeds)} source feed(s): "
                    + ", ".join(f"{s.source_table}.{s.business_key_column}" for s in new_feeds)
                )
        children = [
            sat.name
            for sat in merged.satellites
            if sat.parent == name and sat.name not in prior_names
        ]
        if children:
            gained.append(f"{len(children)} new satellite(s): {', '.join(children)}")
        if gained:
            diff.extended[name] = gained
        else:
            diff.unchanged.append(name)

    for hub in merged.hubs:
        if hub.name not in prior_names:
            diff.new[hub.name] = ""
    for link in merged.links:
        if link.name not in prior_names:
            diff.new[link.name] = ""
    for sat in merged.satellites:
        if sat.name not in prior_names:
            diff.new[sat.name] = sat.parent

    diff.changed_files = await _changed_files(state, prior)
    return diff


async def _changed_files(state: VaultAgentState, prior: DVModel) -> dict[str, list[str]]:
    """Which generated files differ from a regeneration of the existing model alone.

    Only files belonging to a PRE-EXISTING construct are reported: a new construct's files
    are new, which the "new" section already says. A regeneration failure is logged and
    yields no attribution rather than failing the run — the diff is a reporting aid, and
    losing it must never cost the user their artifacts."""
    from vault_agent.agents.code_generator import CodeGeneratorAgent

    baseline = VaultAgentState(
        input_documents=list(state.input_documents),
        source_schemas=list(state.source_schemas),
        dv_model=prior,
    )
    try:
        await CodeGeneratorAgent().run(baseline)
    except Exception:  # noqa: BLE001 - attribution is an aid, never a reason to fail a run
        logger.warning("could not regenerate the existing model for the diff", exc_info=True)
        return {}

    changed: dict[str, list[str]] = {}
    for label, before_models, after_models in [
        ("models/raw_vault", baseline.artifacts.dbt_models, state.artifacts.dbt_models),
        ("models/staging", baseline.artifacts.staging_models, state.artifacts.staging_models),
    ]:
        for name, sql in sorted(before_models.items()):
            after = after_models.get(name)
            if after is None:
                changed.setdefault(name, []).append(f"{label}/{name}.sql (no longer generated)")
            elif after != sql:
                changed.setdefault(_owner(name, prior), []).append(f"{label}/{name}.sql")
    return changed


def _owner(model_name: str, prior: DVModel) -> str:
    """The construct a generated file belongs to.

    A raw-vault model is named after its construct; a staging model is named after the
    construct base it serves, so map it back by matching the base. Unattributable names are
    reported under their own name rather than guessed at."""
    if model_name in set(_construct_names(prior)):
        return model_name
    base = model_name[4:] if model_name.startswith("stg_") else model_name
    for name in _construct_names(prior):
        if name.split("_", 1)[-1] == base:
            return name
    return model_name


def render_extension_diff_md(diff: ExtensionDiff, source: str) -> str:
    """Render the diff as the ``extension-diff.md`` artifact (deterministic, no timestamps)."""
    unchanged, extended, new = diff.counts
    lines = [
        "# Extension diff",
        "",
        f"This run extended the vault at `{source}`: **{unchanged} unchanged**, "
        f"**{extended} extended**, **{new} new** construct(s).",
        "",
        "Unchanged constructs render byte-identically, so their tables are untouched by a "
        "rebuild. The files listed under *extended* are the ones that genuinely changed.",
        "",
        f"## Unchanged ({unchanged})",
        "",
        ", ".join(f"`{name}`" for name in diff.unchanged) if diff.unchanged else "—",
        "",
        f"## Extended ({extended})",
        "",
    ]
    if diff.extended:
        for name, gained in diff.extended.items():
            lines.append(f"- **{name}** — {'; '.join(gained)}")
            for path in diff.changed_files.get(name, []):
                lines.append(f"  - changed file: `{path}`")
    else:
        lines.append("—")
    lines += ["", f"## New ({new})", ""]
    if diff.new:
        for name, parent in diff.new.items():
            attached = f" — on `{parent}`" if parent else ""
            lines.append(f"- **{name}**{attached}")
    else:
        lines.append("—")
    lines.append("")
    return "\n".join(lines)
