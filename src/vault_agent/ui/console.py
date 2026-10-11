"""The state-driven console (WP68): a command grammar over a run's state, no model call.

Everything here reads — the state, the catalogues, the steering registry, the CLI's own help —
and returns text. A „what if“ names the CLI command it would be and runs nothing. Item numbers
are positions in the checkpoint's queue; nothing branches on a human-readable message.
"""
from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from typing import Any, cast

from vault_agent.agents.orchestrator import ReviewItem, assemble_review_queue
from vault_agent.rules.catalogue import FLAGS, GATES
from vault_agent.rules.dv2_rules import active_modeling_rules
from vault_agent.state import Link, VaultAgentState

Kind = str  # "answer" | "help" | "unknown" | "unavailable"


@dataclass
class ConsoleAnswer:
    text: str
    kind: Kind = "answer"
    refs: list[dict[str, str]] = field(default_factory=list)
    command: str | None = None

    def json(self) -> dict[str, Any]:
        return {"text": self.text, "kind": self.kind, "refs": self.refs, "command": self.command}


HELP = """Commands (everything is read from the run's state; nothing here runs or decides):
  status                         the run, its attempts, what the checkpoint holds
  items [decisions|disclosures]  the review queue, numbered
  explain <n | asset | CODE | flag_kind>   what an item, a gate or a flag means and how to answer it
  why <construct>                every issue, flag, item and retirement that concerns a construct
  show <construct>               a hub, link or satellite as the model carries it, neighbours too
  gates | gate <CODE>            the validator's catalogue, and which gates fired here
  flags                          the typed flags of this run, by kind
  steering [id]                  the prompt steering the modeler was given, with its provenance
  cli                            the CLI commands this run is equivalent to
  what if accept | discard | owner <asset>=<Name <email>> | resolve <concept>=<answer>
                                 the CLI command that action would be — without running it
Free text that names a construct, a code, a flag kind or an item's asset is routed accordingly."""

_REVIEW_KINDS: dict[str, str] = {
    "contract_owner": "a contract still carries the placeholder owner; name a real one "
    "(`--owner 'asset=Name <email>'`, or the owner field in the Review tab). Blocking.",
    "validation_error": "a validator gate refused the model after the last attempt; the run "
    "reached the checkpoint with the error standing. Accepting proceeds without a mappings "
    "section; re-modelling means a new run. Blocking.",
    "validation_warning": "a validator gate flagged something worth a look; it does not block.",
    "review_flag": "a typed flag an agent raised — provenance (what was assumed, inferred, "
    "dropped or declined) or a question only a human can answer, by its kind.",
}


def _ref(perspective: str, label: str) -> dict[str, str]:
    return {"perspective": perspective, "label": label}


def _constructs(state: VaultAgentState) -> dict[str, tuple[str, Any]]:
    m = state.dv_model
    out: dict[str, tuple[str, Any]] = {}
    out.update({h.name: ("hub", h) for h in m.hubs})
    out.update({link.name: ("link", link) for link in m.links})
    out.update({s.name: ("satellite", s) for s in m.satellites})
    return out


def _hub_names(link: Link) -> list[str]:
    return [h if isinstance(h, str) else f"{h.hub}:{h.role}" if h.role else h.hub
            for h in link.connected_hubs]


def _resume_help() -> dict[str, str]:
    """The `resume` command's own option help, through click — never a second description."""
    import click
    import typer.main

    from vault_agent import cli

    group = cast(click.Group, typer.main.get_command(cli.app))
    command = group.commands["resume"]
    return {"/".join(p.opts): (getattr(p, "help", None) or "") for p in command.params}


class Console:
    def __init__(self, state: VaultAgentState, meta: dict[str, Any] | None) -> None:
        self.state = state
        self.meta = meta or {}
        self.queue = assemble_review_queue(state)
        self.constructs = _constructs(state)

    # ----- dispatch --------------------------------------------------------------------------
    def answer(self, text: str) -> ConsoleAnswer:
        words = text.strip().split()
        if not words:
            return ConsoleAnswer(HELP, kind="help")
        head, rest = words[0].lower(), " ".join(words[1:])
        if head in ("help", "?"):
            return ConsoleAnswer(HELP, kind="help")
        if head == "status":
            return self.status()
        if head == "items":
            return self.items(rest.lower() or None)
        if head == "explain" and rest:
            return self.explain(rest)
        if head == "why" and rest:
            return self.why(rest)
        if head == "show" and rest:
            return self.show(rest)
        if head == "gates":
            return self.gates()
        if head == "gate" and rest:
            return self.explain(rest.upper())
        if head == "flags":
            return self.flags()
        if head == "steering":
            return self.steering(rest or None)
        if head == "cli":
            return self.cli()
        if head == "what" and rest.lower().startswith("if "):
            return self.what_if(rest[3:].strip())
        # free text: a construct, a code, a flag kind or an item's asset
        token = text.strip()
        if token in self.constructs:
            return self.show(token)
        if token.upper() in GATES or token.lower() in FLAGS:
            return self.explain(token)
        if any(item.asset == token for item in self.queue.items):
            return self.explain(token)
        return ConsoleAnswer(f"I do not know „{token}“. Type `help` for the commands.\n\n{HELP}",
                             kind="unknown")

    # ----- answers ---------------------------------------------------------------------------
    def status(self) -> ConsoleAnswer:
        s = self.state
        status = self.meta.get("status", "in memory")
        errors = [i for i in s.validation_report.issues if i.severity == "error"]
        warnings = [i for i in s.validation_report.issues if i.severity == "warning"]
        lines = [
            f"run: {self.meta.get('id', '(no run.json)')} — {status}",
            f"modeler attempts: {s.modeling_attempts}; validation "
            f"{'passed' if s.validation_report.passed else 'not passed'} "
            f"({len(errors)} errors, {len(warnings)} warnings)",
            f"model: {len(s.dv_model.hubs)} hubs, {len(s.dv_model.links)} links, "
            f"{len(s.dv_model.satellites)} satellites"
            + (f"; {len(s.existing_model.hubs)} existing hubs (brownfield)"
               if s.existing_model else ""),
            f"checkpoint: {len(self.queue.decisions)} decisions, "
            f"{len(self.queue.disclosures)} disclosures, "
            f"{'blocked' if self.queue.requires_signoff else 'not blocked'}",
            f"flags: {len(s.flags)}; retired constructs: {len(s.retired_constructs)}; "
            f"contracts: {len(s.artifacts.contracts)}",
        ]
        refs = [_ref("run", "open Run")]
        if status == "paused":
            refs.append(_ref("review", "open Review"))
        return ConsoleAnswer("\n".join(lines), refs=refs)

    def items(self, which: str | None) -> ConsoleAnswer:
        items = self.queue.items
        lines = []
        for n, item in enumerate(items, 1):
            if which == "decisions" and item.role != "decision":
                continue
            if which == "disclosures" and item.role != "disclosure":
                continue
            asset = f" [{item.asset}]" if item.asset else ""
            lines.append(f"{n}. ({item.role}, {item.kind}){asset} {item.summary}")
        if not lines:
            return ConsoleAnswer("The queue holds no such items.",
                                 refs=[_ref("review", "open Review")])
        head = (f"{len(self.queue.decisions)} decisions, {len(self.queue.disclosures)} "
                "disclosures; numbers are positions in the queue (explain <n>):")
        return ConsoleAnswer(head + "\n" + "\n".join(lines), refs=[_ref("review", "open Review")])

    def explain(self, what: str) -> ConsoleAnswer:
        token = what.strip()
        if token.isdigit():
            n = int(token)
            if 1 <= n <= len(self.queue.items):
                return self._explain_item(n, self.queue.items[n - 1])
            count = len(self.queue.items)
            return ConsoleAnswer(f"The queue has {count} items; there is no item {n}.",
                                 kind="unknown")
        if token.upper() in GATES:
            return self._explain_gate(token.upper())
        if token.lower() in FLAGS:
            return self._explain_flag_kind(token.lower())
        matches = [(n, i) for n, i in enumerate(self.queue.items, 1) if i.asset == token]
        if matches:
            return ConsoleAnswer("\n\n".join(self._explain_item(n, i).text for n, i in matches),
                                 refs=[_ref("review", "open Review")])
        if token in self.constructs:
            return self.why(token)
        return ConsoleAnswer(f"Nothing named „{token}“: not an item number, an asset, a gate code "
                             "or a flag kind. Try `items`, `gates` or `flags`.", kind="unknown")

    def _explain_item(self, n: int, item: ReviewItem) -> ConsoleAnswer:
        lines = [f"item {n}: {item.summary}",
                 f"kind: {item.kind} — role: {item.role} ("
                 + ("needs an answer before the model is agreed" if item.role == "decision"
                    else "provenance; nothing to answer") + ")",
                 f"meaning: {_REVIEW_KINDS.get(item.kind, '')}".rstrip(": ")]
        if item.asset:
            lines.append(f"asset: {item.asset}")
        if item.source:
            lines.append(f"raised by: {item.source}")
        if item.detail:
            lines.append(f"detail: {item.detail}")
        refs = [_ref("review", "open Review")]
        if item.kind == "contract_owner" and item.asset:
            spec = shlex.quote(item.asset + "=Name <email>")
            lines.append(f"to answer: `vault-agent resume --out <run> --owner {spec}` — the owner "
                         "field in the Review tab.")
        if item.kind in ("validation_error", "validation_warning"):
            code = item.group if item.group in GATES else None
            issues = [i for i in self.state.validation_report.issues
                      if i.construct == item.asset and (code is None or i.code == code)]
            for issue in issues:
                lines.append(f"gate {issue.code}: {GATES.get(issue.code, '')}")
                if issue.remedy:
                    lines.append(f"remedy: {issue.remedy}")
                if issue.retires:
                    lines.append(f"retires: {', '.join(issue.retires)}")
            lines.append(f"after {self.state.modeling_attempts} modeler attempt(s); "
                         "manual chapter 8.")
            refs.append(_ref("model", "open Model"))
        if item.kind == "review_flag":
            flags = [f for f in self.state.flags if f.asset == item.asset and f.kind == item.group]
            kind = item.group if item.group in FLAGS else None
            if kind:
                lines.append(f"flag kind {kind}: {FLAGS[kind]}")
            for f in flags:
                if f.reason:
                    lines.append(f"reason: {f.reason}")
        return ConsoleAnswer("\n".join(lines), refs=refs)

    def _explain_gate(self, code: str) -> ConsoleAnswer:
        fired = [i for i in self.state.validation_report.issues if i.code == code]
        lines = [f"{code}: {GATES[code]}",
                 "severity: " + ("error — refuses the model and feeds the re-model loop"
                                 if code.startswith("E_")
                                 else "warning — reported, does not block")]
        if fired:
            lines.append(f"fired in this run on: {', '.join(i.construct for i in fired)}")
            for i in fired:
                if i.remedy:
                    lines.append(f"remedy for {i.construct}: {i.remedy}")
        else:
            lines.append("did not fire in this run (as the state stands).")
        lines.append("manual: operations chapter 8.2.")
        return ConsoleAnswer("\n".join(lines), refs=[_ref("model", "open Model")] if fired else [])

    def _explain_flag_kind(self, kind: str) -> ConsoleAnswer:
        here = [f for f in self.state.flags if f.kind == kind]
        lines = [f"{kind}: {FLAGS[kind]}"]
        if here:
            lines.append(f"raised {len(here)} time(s) here: "
                         + ", ".join(f"{f.asset or '—'} ({f.agent})" for f in here[:12]))
        else:
            lines.append("not raised in this run.")
        return ConsoleAnswer("\n".join(lines), refs=[_ref("review", "open Review")] if here else [])

    def why(self, name: str) -> ConsoleAnswer:
        s = self.state
        issues = [i for i in s.validation_report.issues if name in i.construct.split(", ")]
        flags = [f for f in s.flags if f.asset == name]
        items = [(n, i) for n, i in enumerate(self.queue.items, 1) if i.asset == name]
        retired = [r for r in s.retired_constructs if r.name == name]
        if name not in self.constructs and not (issues or flags or items or retired):
            return ConsoleAnswer(f"Nothing in the state concerns „{name}“.", kind="unknown")
        lines = [f"{name}: {len(issues)} issue(s), {len(flags)} flag(s), {len(items)} review "
                 f"item(s), {len(retired)} retirement(s); modeler attempts so far: "
                 f"{s.modeling_attempts}"]
        for i in issues:
            lines.append(f"- {i.severity} {i.code}: {GATES.get(i.code, '')}")
            lines.append(f"  message: {i.message}")
            if i.remedy:
                lines.append(f"  remedy: {i.remedy}")
            if i.retires:
                lines.append(f"  retires: {', '.join(i.retires)}")
        for f in flags:
            reason = f" (reason {f.reason})" if f.reason else ""
            lines.append(f"- flag {f.kind}{reason} by {f.agent}: {FLAGS.get(f.kind, '')}")
        for n, item in items:
            lines.append(f"- review item {n} ({item.role}, {item.kind}): {item.summary}")
        for r in retired:
            lines.append(f"- retired as a {r.kind} by {r.code} in attempt {r.attempt}")
        refs = [_ref("model", "open Model")]
        if items:
            refs.append(_ref("review", "open Review"))
        return ConsoleAnswer("\n".join(lines), refs=refs)

    def show(self, name: str) -> ConsoleAnswer:
        if name not in self.constructs:
            hubs = ", ".join(h.name for h in self.state.dv_model.hubs)
            return ConsoleAnswer(f"No construct named „{name}“ in the model. Hubs: {hubs}",
                                 kind="unknown")
        kind, c = self.constructs[name]
        m = self.state.dv_model
        lines = [f"{kind} {name}: {c.description}"]
        if kind == "hub":
            key = ", ".join(c.business_key_columns) if c.business_key_columns else c.business_key
            lines.append(f"business key: {key}; source entity: {c.source_entity}")
            if c.sources:
                feeds = "; ".join(f"{f.source_table}.{f.business_key_column}" for f in c.sources)
                lines.append(f"feeds: {feeds}")
            sats = [s.name for s in m.satellites if s.parent == name]
            links = [link.name for link in m.links
                     if name in [h.split(":")[0] for h in _hub_names(link)]]
            lines.append(f"satellites: {', '.join(sats) or 'none'}")
            lines.append(f"links: {', '.join(links) or 'none'}")
        elif kind == "link":
            lines.append(f"type: {c.link_type}; participations: {', '.join(_hub_names(c))}")
            if c.driving_key:
                lines.append(f"driving key: {', '.join(c.driving_key)}")
            if c.event_timestamp:
                lines.append(f"event timestamp: {c.event_timestamp}")
            sats = [s.name for s in m.satellites if s.parent == name]
            lines.append(f"satellites: {', '.join(sats) or 'none'}")
        else:
            lines.append(f"parent: {c.parent}; type: {c.sat_type}; attributes "
                         f"({len(c.attributes)}): " + ", ".join(c.attributes))
            if c.source_table:
                lines.append(f"source table: {c.source_table}")
            if c.child_dependent_key:
                lines.append(f"child dependent key: {', '.join(c.child_dependent_key)}")
        if c.requirement_ids:
            lines.append(f"requirements: {', '.join(c.requirement_ids)}")
        concerns = self.why(name)
        if concerns.kind == "answer" and "\n" in concerns.text:
            lines.append("concerns: " + concerns.text.split("\n", 1)[1].replace("\n", "\n  "))
        return ConsoleAnswer("\n".join(lines), refs=[_ref("model", "open Model")])

    def gates(self) -> ConsoleAnswer:
        fired = {i.code for i in self.state.validation_report.issues}
        lines = [f"{len(GATES)} gates; * = fired in this run"]
        for code, meaning in GATES.items():
            lines.append(f"{'*' if code in fired else ' '} {code}: {meaning}")
        return ConsoleAnswer("\n".join(lines))

    def flags(self) -> ConsoleAnswer:
        counts: dict[str, int] = {}
        for f in self.state.flags:
            counts[f.kind] = counts.get(f.kind, 0) + 1
        if not counts:
            return ConsoleAnswer("No flags in this run.")
        lines = [f"{len(self.state.flags)} flag(s) by kind:"]
        for kind, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {kind} ×{n}: {FLAGS.get(kind, '')}")
        return ConsoleAnswer("\n".join(lines), refs=[_ref("review", "open Review")])

    def steering(self, rule_id: str | None) -> ConsoleAnswer:
        rules = active_modeling_rules()
        if rule_id:
            hits = [r for r in rules if r.id == rule_id]
            if not hits:
                return ConsoleAnswer(f"No active steering rule „{rule_id}“. Ids: "
                                     + ", ".join(r.id for r in rules), kind="unknown")
            r = hits[0]
            return ConsoleAnswer(f"{r.id}: {r.text}\nbackstop: {r.backstop or 'none'}\n"
                                 f"origin: {r.origin or '—'}")
        lines = [f"{len(rules)} steering rules in the modeler prompt (model-compensation, "
                 "ablatable; gates are not among them):"]
        for r in rules:
            lines.append(f"- {r.id}" + (f" [backstop {r.backstop}]" if r.backstop else "")
                         + f": {r.origin or r.text}")
        return ConsoleAnswer("\n".join(lines))

    def cli(self) -> ConsoleAnswer:
        eq = self.meta.get("cli_equivalents") or []
        if not eq:
            return ConsoleAnswer("No run.json for this state, so no recorded CLI equivalents.")
        return ConsoleAnswer("This run so far, as the terminal would run it:\n" + "\n".join(eq),
                             refs=[_ref("run", "open Run")])

    def what_if(self, action: str) -> ConsoleAnswer:
        out = self.meta.get("out_dir", "<run>")
        base = ["vault-agent", "resume", "--out", str(out)]
        help_ = _resume_help()
        words = action.split(maxsplit=1)
        verb = words[0].lower() if words else ""
        arg = words[1].strip() if len(words) > 1 else ""
        if verb == "accept":
            cmd = base + ["--accept"]
            effect = help_.get("--accept", "")
            extra = (" The checkpoint is blocked (a contract without an owner or a standing "
                     "error): accepting proceeds with the standard unattended decisions."
                     if self.queue.requires_signoff else "")
        elif verb == "discard":
            cmd = base + ["--discard"]
            effect, extra = help_.get("--discard", ""), ""
        elif verb == "owner" and "=" in arg:
            cmd = base + ["--owner", arg]
            effect, extra = help_.get("--owner", ""), ""
        elif verb == "resolve" and "=" in arg:
            cmd = base + ["--resolve", arg]
            effect, extra = help_.get("--resolve", ""), ""
        else:
            return ConsoleAnswer("what if accept | discard | owner <asset>=<Name <email>> | "
                                 "resolve <concept>=<answer>", kind="unknown")
        command = shlex.join(cmd)
        return ConsoleAnswer(f"That would be:\n  {command}\n{effect}{extra}\nNothing ran; the "
                             "Review tab performs it through the same code path.",
                             command=command, refs=[_ref("review", "open Review")])


def answer(state: VaultAgentState, meta: dict[str, Any] | None, text: str) -> ConsoleAnswer:
    return Console(state, meta).answer(text)
