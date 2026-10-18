"""WP80 — the vault by subject area: a reading of what each construct's stage reads.

A construct's subject areas are the schemas of the relations its staging model reads: a hub's
bound relation, a link's bound relation, a satellite's own ``source_table`` or its parent's
relation, a multi-source hub's feeds. The model carries no subject-area field and needs none —
the staging generator decided the bindings (``bind_sources``, WP7/WP77) and the catalogue
carries the schema of every earlier increment's table (WP74). Two inputs answer the question:
the staging metadata of a generated project (``automatedv_yaml["staging"]``, the record of what
the project reads, including the source mapper's re-bind), or — before generation — the same
binding recomputed the way the generator computes it. Nothing here is a flag, a gate or a model
statement; changing a binding at the checkpoint is the only thing that moves a construct.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vault_agent.agents.code_generator import _sat_staging_model
from vault_agent.agents.staging_generator import (
    bind_sources,
    collect_staging_specs,
    construct_stage_name,
    legacy_feeds,
)
from vault_agent.rules.dv2_rules import normalize_identifier, satellite_feed
from vault_agent.state import DVModel, SourceTable

NO_SCHEMA_AREA = "(no schema)"  # relations declared without a schema: the seed world
UNBOUND_AREA = "(unbound)"  # stages with an inferred binding: what a human must still provide


@dataclass
class SubjectArea:
    """One area: its members by construct kind, in model order, and the hubs or links of other
    areas its links and satellites reach (``neighbours``), in model order."""

    name: str
    increment: bool = False
    hubs: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    satellites: list[str] = field(default_factory=list)
    neighbours: list[str] = field(default_factory=list)

    def members(self) -> set[str]:
        return {*self.hubs, *self.links, *self.satellites}

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "increment": self.increment,
            "hubs": list(self.hubs),
            "links": list(self.links),
            "satellites": list(self.satellites),
            "neighbours": list(self.neighbours),
        }


def _relations_from_metadata(staging: dict[str, Any]) -> dict[str, tuple[str, bool]]:
    """stage name -> (relation, declared?) from a generated project's staging metadata."""
    relations: dict[str, tuple[str, bool]] = {}
    for name, meta in staging.items():
        if not isinstance(meta, dict):
            continue
        source_model = meta.get("source_model")
        if isinstance(source_model, dict):
            source_model = next(iter(source_model.values()), "")
        relations[name] = (str(source_model or ""), meta.get("source_binding") == "declared")
    return relations


def _relations_recomputed(
    model: DVModel,
    tables: list[SourceTable],
    existing: DVModel | None,
    carried_bindings: dict[str, str] | None,
) -> dict[str, tuple[str, bool]]:
    """The generator's own binding pass, without the mapper's overrides (a state before
    generation has none yet)."""
    specs = collect_staging_specs(model, legacy_feeds(existing))
    bind_sources(specs, tables, None, None, carried_bindings)
    return {name: (spec.source_model, spec.bound) for name, spec in specs.items()}


def subject_areas(
    model: DVModel,
    source_schemas: list[SourceTable],
    carried: list[SourceTable] | None = None,
    staging: dict[str, Any] | None = None,
    existing: DVModel | None = None,
    carried_bindings: dict[str, str] | None = None,
) -> list[SubjectArea]:
    """Partition the model's constructs into subject areas (spec §2.1) with their neighbours
    (§2.2). Areas are ordered alphabetically, ``(no schema)`` and ``(unbound)`` last; an area is
    the increment's when one of its relations is in ``source_schemas``."""
    own_tables = {normalize_identifier(s.table) for s in source_schemas}
    tables = list(source_schemas) + [
        t for t in (carried or []) if normalize_identifier(t.table) not in own_tables
    ]
    schema_of = {normalize_identifier(t.table): t.schema_name for t in tables}
    increment = {normalize_identifier(t.table) for t in source_schemas}
    relations = (
        _relations_from_metadata(staging) if staging
        else _relations_recomputed(model, tables, existing, carried_bindings)
    )
    areas: dict[str, SubjectArea] = {}

    def area_of_relation(relation: str) -> str:
        key = normalize_identifier(relation)
        if key not in schema_of:
            return UNBOUND_AREA
        return schema_of[key] or NO_SCHEMA_AREA

    def area_of_stage(stage: str) -> str | None:
        found = relations.get(stage)
        if found is None:
            return None
        relation, declared = found
        return area_of_relation(relation) if declared else UNBOUND_AREA

    def place(name: str, kind: str, placements: list[tuple[str, str | None]]) -> None:
        """Put the construct into each (area, relation key) pair's area once; an area is the
        increment's when the relation that put a construct THERE is one of the run's own —
        a multi-source hub's Sales feed says nothing about its Person feed's area."""
        for area_name in dict.fromkeys(area_name for area_name, _ in placements):
            area = areas.setdefault(area_name, SubjectArea(name=area_name))
            getattr(area, kind).append(name)
            if any(a == area_name and key in increment for a, key in placements):
                area.increment = True

    hub_areas: dict[str, list[str]] = {}
    hubs_by_name = {hub.name: hub for hub in model.hubs}
    placements: list[tuple[str, str | None]]
    for hub in model.hubs:
        if hub.sources:
            placements = [
                (area_of_relation(source.source_table), normalize_identifier(source.source_table))
                for source in hub.sources
            ]
        else:
            stage = construct_stage_name(hub.name)
            relation = relations.get(stage, ("", False))[0]
            placements = [(area_of_stage(stage) or UNBOUND_AREA, normalize_identifier(relation))]
        hub_areas[hub.name] = list(dict.fromkeys(a for a, _ in placements))
        place(hub.name, "hubs", placements)

    link_areas: dict[str, list[str]] = {}
    for link in model.links:
        stage = construct_stage_name(link.name)
        relation = relations.get(stage, ("", False))[0]
        link_areas[link.name] = [area_of_stage(stage) or UNBOUND_AREA]
        place(link.name, "links", [(link_areas[link.name][0], normalize_identifier(relation))])

    parent_areas = {**hub_areas, **link_areas}
    for sat in model.satellites:
        parent_hub = hubs_by_name.get(sat.parent)
        feed = satellite_feed(sat, parent_hub)
        if feed is not None:
            placements = [
                (area_of_relation(feed.source_table), normalize_identifier(feed.source_table))
            ]
        else:
            stage = _sat_staging_model(sat)
            own = area_of_stage(stage)
            if own is not None:
                placements = [(own, normalize_identifier(relations.get(stage, ("", False))[0]))]
            else:
                # A satellite without its own stage on a multi-source hub (one per feed), or an
                # unknown parent: it goes where the parent goes, and says nothing about the
                # increment itself.
                placements = [(a, None) for a in parent_areas.get(sat.parent, [])]
        if placements:
            place(sat.name, "satellites", placements)

    order = {
        name: index
        for index, name in enumerate(
            [hub.name for hub in model.hubs] + [link.name for link in model.links]
            + [sat.name for sat in model.satellites]
        )
    }
    links_by_name = {link.name: link for link in model.links}
    sats_by_name = {sat.name: sat for sat in model.satellites}
    for area in areas.values():
        members = area.members()
        reached: set[str] = set()
        for name in area.links:
            reached.update(ref.hub for ref in links_by_name[name].hub_refs)
        for name in area.satellites:
            reached.add(sats_by_name[name].parent)
        area.neighbours = sorted(
            (n for n in reached if n not in members and n in order), key=order.__getitem__
        )

    def rank(area: SubjectArea) -> tuple[int, str]:
        return ({NO_SCHEMA_AREA: 1, UNBOUND_AREA: 2}.get(area.name, 0), area.name)

    return sorted(areas.values(), key=rank)
