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
    every extension run to no benefit."""
    if existing is None:
        return ""
    lines = [
        "## The existing vault you are EXTENDING",
        "",
        "These constructs already exist and are IMMUTABLE. They hold live history: renaming,"
        " re-keying or re-shaping any of them is a migration this agent never performs.",
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
        "Emit ONLY the delta:",
        "",
        "1. NEW hubs, links and satellites the requirements introduce. Attach them to the "
        "existing constructs above by their exact names — never re-invent or rename a "
        "concept that already exists.",
        "2. An existing hub RE-STATED BY NAME carrying only its ADDITIONAL `sources` "
        "entries, when a new source system feeds a concept the vault already models.",
        "",
        "Do NOT re-emit existing links or satellites, and do not restate an existing hub for "
        "any other reason. If new attributes belong to a concern an existing satellite "
        "already covers, put them in a NEW satellite on the same parent — an existing "
        "satellite's payload is fixed, because every stored row would otherwise need "
        "backfilling.",
    ]
    return "\n" + "\n".join(lines) + "\n"
