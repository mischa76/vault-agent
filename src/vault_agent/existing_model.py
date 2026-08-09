"""Loader for a previously generated vault's logical model (WP23 §2.1, brownfield mode).

Brownfield mode extends an existing vault instead of modelling into an empty target. The
existing model is an INPUT, not a discovery: ``run --existing <dir|file>`` reads the
``metadata/dv_model.yml`` a previous run wrote (:data:`DV_MODEL_FILENAME`) and hands it to
the pipeline as ``state.existing_model``.

Why not ``automatedv.yml``: the charter's §3.1 first guess was to round-trip the rendered
AutomateDV metadata, which every run already writes. It cannot work — that file is the
*rendered macro* view (source_model, src_pk, src_nk, …) and has no descriptions,
requirement_ids, ``sat_type``, driving keys, ``source_table`` or ``Hub.sources``.
Reconstructing a DVModel from it would silently invent the fields it lost, which is exactly
what this project does not do. So the logical dump became its own output and this loader
reads that; a pre-WP23 output directory is an attributable error telling the user to
regenerate once, never a guess.

Errors follow the house loader style (:mod:`vault_agent.source_schema`): every failure names
the file and the problem, so a wrong ``--existing`` costs a message rather than a traceback
or, worse, a plausible-looking wrong model.
"""
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from vault_agent.state import DVModel

# The logical model a run writes under its output ``metadata/`` directory, and the file a
# later extension run reads back. One definition, imported by the writer and the loader.
DV_MODEL_FILENAME = "dv_model.yml"


def load_existing_model(path: Path) -> DVModel | None:
    """Load the logical model of a previously generated vault.

    ``path`` is either an output directory (``metadata/dv_model.yml`` is read inside it) or
    the YAML file itself. Returns ``None`` for an empty/``null`` document — the ADR-0004
    inertness convention, so an empty file means "greenfield" rather than an error.

    Raises ``ValueError`` naming the file and the problem for: a missing path, a directory
    without the file (the pre-WP23 case, with the fix in the message), unreadable or
    malformed YAML, a document that is not a mapping, and a mapping that does not validate
    as a :class:`~vault_agent.state.DVModel`.
    """
    source = _resolve(path)
    try:
        raw = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"{source}: could not be read ({exc})") from exc
    try:
        document: Any = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"{source}: not valid YAML ({exc})") from exc

    if document is None:
        return None  # empty file: inert, same convention as an empty source schema
    if not isinstance(document, dict):
        raise ValueError(
            f"{source}: expected a mapping with hubs/links/satellites keys, got "
            f"{type(document).__name__}"
        )
    try:
        model = DVModel.model_validate(document)
    except ValidationError as exc:
        raise ValueError(f"{source}: not a valid Data Vault model ({exc})") from exc

    if not (model.hubs or model.links or model.satellites):
        return None  # a model with no constructs is the same as no model
    return model


def _resolve(path: Path) -> Path:
    """The YAML file to read, from a directory or a direct file path."""
    if not path.exists():
        raise ValueError(f"{path}: no such file or directory")
    if path.is_dir():
        candidate = path / "metadata" / DV_MODEL_FILENAME
        if not candidate.is_file():
            raise ValueError(
                f"{path}: not a vault-agent output directory carrying "
                f"metadata/{DV_MODEL_FILENAME}. Outputs generated before this file existed "
                f"cannot be extended — regenerate that vault once with the current version "
                f"(the generator is deterministic, so the regenerated project is identical), "
                f"then point --existing at the new output"
            )
        return candidate
    return path


def render_extension_prompt_section(existing: DVModel | None) -> str:
    """Render the existing vault as a modeler prompt section; ``''`` when greenfield.

    Mirrors :func:`vault_agent.grounding.render_schema_prompt_section`: returning ``''``
    keeps the system prompt byte-identical for a greenfield run, which is what makes the
    WP16 steering fixture and prompt caching unaffected by this WP.

    The inventory is deliberately COMPACT — names, keys, grain, types — not a full dump.
    The modeler needs to recognise what exists and attach to it; it does not need the
    existing descriptions or requirement traces, and sending them would cost tokens on
    every extension run to no benefit.

    **The register was rewritten in WP30.2, and the reason is measured** (docs/log.md,
    2026-08-09). This section used to open with "IMMUTABLE … a migration this agent never
    performs" and close with "Emit ONLY the delta … Do NOT re-emit" — every sentence a
    prohibition. Arm B then built **0 of 37** links spanning two domains where arm A built 16
    from the same landscape, and invented a local hub for a concept this very inventory listed
    by name. The instruction to do otherwise was present at five levels — the schema's foreign
    key, the requirements text, this section's own "attach by their exact names", a ratified
    resolver merge, and finally an explicit steering rule that changed nothing.

    The rules did not change; only which of them the text leads with. Two things are genuinely
    fixed — an existing construct is never renamed or re-keyed, and an existing satellite's
    payload never grows — and they are still stated, at the end, as the two exceptions they
    are. What comes first now is what the section is actually for: these hubs are endpoints,
    and a link to one changes nothing about it."""
    if existing is None:
        return ""
    lines = [
        "## The vault you are extending — these hubs are yours to build against",
        "",
        "Each construct below already exists and is a CONNECTION POINT for what you are adding"
        " now. Building a link to one of these hubs does not change that hub — it is a new"
        " construct, and it is the main thing this section exists for.",
        "",
    ]
    for hub in existing.hubs:
        feeds = (
            f"; fed by {', '.join(s.source_table for s in hub.sources)}"
            if hub.sources
            else ""
        )
        lines.append(f"- hub **{hub.name}** — business key `{hub.business_key}`{feeds}")
    for link in existing.links:
        grain = ", ".join(
            ref.hub if ref.role is None else f"{ref.hub}:{ref.role}" for ref in link.hub_refs
        )
        driving = f"; driving key {', '.join(link.driving_key)}" if link.driving_key else ""
        lines.append(f"- link **{link.name}** — connects {grain}{driving}")
    for sat in existing.satellites:
        lines.append(f"- satellite **{sat.name}** — {sat.sat_type}, on {sat.parent}")
    lines += [
        "",
        "Wherever this increment's requirements reference something one of those hubs already "
        "holds — a foreign key, a concept the requirements call maintained elsewhere, any "
        "reference they say must be preserved so the areas can be joined later — model that "
        "reference as a LINK to that hub, by its exact name. Nobody adds those links in a "
        "later increment; if you do not build them now, the vault simply never has them.",
        "",
        "Emit what does not exist yet:",
        "",
        "1. NEW hubs, links and satellites — INCLUDING links whose participants are hubs "
        "listed above, and links between an existing hub and one you are adding now. Use the "
        "exact names above; never re-invent or rename a concept that already exists.",
        "2. An existing hub RE-STATED BY NAME carrying only its ADDITIONAL `sources` "
        "entries, when a new source system feeds a concept the vault already models.",
        "",
        "Two things are fixed, and only two. An existing construct is never renamed, re-keyed "
        "or re-shaped — that is a migration this agent does not perform. And an existing "
        "satellite's payload never grows: if new attributes belong to a concern an existing "
        "satellite already covers, put them in a NEW satellite on the same parent, because "
        "every stored row would otherwise need backfilling. Beyond those two, do not re-emit "
        "an existing link or satellite unchanged — there is nothing to gain from restating it.",
    ]
    return "\n" + "\n".join(lines) + "\n"
