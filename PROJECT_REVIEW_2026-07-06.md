# Projekt-Review vault-agent — Stand 2026-07-06

> **Update 2026-07-07:** P1, P2 (Härtungs-Batch) und P3 (Staging-Generator) sind umgesetzt
> und verifiziert (158→169 Tests grün; P3 zusätzlich end-to-end gegen ein sauberes
> PostgreSQL härtegetestet, siehe CLAUDE.md-Milestone). P5 wurde durch P1 miterledigt.
> Die verbleibenden Punkte (P4, P6–P10 sowie die Deferrals) sind als implementierungsreife
> Work Packages voll spezifiziert: `docs/architecture/backlog-2026-07/` (WP1–WP8 + Kick-offs).

Umfang: Doku (ADRs, Specs, READMEs, Methodology), Code (src/vault_agent, tests), Demo, offene Punkte.
Verifiziert: 151 Tests grün in <5 s ohne API-Key; `ruff check .` sauber; grösste Datei
`agents/code_generator.py` mit 447 Zeilen (keine Datei >500). Die im
`ARCHITECTURE_REVIEW_2026-06-13.md` gelisteten Findings H-1 (driving_key), H-2 (Modellstring)
und M-1 (PDF/DOCX-Reader) sind im Code nachweislich behoben — das Dokument ist historisch.

## Gesamtbewertung

Für den Reifegrad ungewöhnlich diszipliniertes Projekt. Die in CLAUDE.md deklarierten
Konventionen sind im Code real eingelöst: `graph.py` enthält nur Orchestrierung, Regeln liegen
in `rules/dv2_rules.py`, jeder LLM-Agent nutzt dasselbe injizierbare Extractor-Protokoll
(testbar ohne Key), deterministische und LLM-Agenten sind sauber getrennt, und der
Postgres-Durchstich ist ein echter End-to-End-Beweis (29 dbt-Tests, idempotent, End-Dating
verifiziert) statt plausiblem SQL. Die ADR-Disziplin (8 ADRs, ehrliche Scope-Grenzen in
ADR-0007/0008, Findings transparent nachgeführt) ist ein Alleinstellungsmerkmal gegenüber
typischen PoCs. Bewertung: solide Basis, produktreif für die Raw-Vault-Schicht im
demonstrierten Umfang — mit zwei struktureller Schulden, die vor weiterem Feature-Ausbau
adressiert werden sollten (siehe P1/P2 unten).

## Stärken

Trennung Orchestrierung/Fachlogik ist real, nicht aspirational. Forced-tool-use statt
Freitext-JSON-Parsing in allen LLM-Aufrufen, mit Re-Validierung per pydantic. Validator und
Generator prüfen sich gegenseitig (Defense in Depth explizit). Grounding ist byte-identisch
inert ohne Schema (Regressionsschutz). Testqualität hoch: exakte Code-/Konstrukt-Assertions,
Graph-Interrupt/Resume gegen echten MemorySaver, keine Smoke-Tests. Doku ehrlich: Gaps und
Deferrals sind benannt statt versteckt.

## Schwächen und Risiken (priorisiert, mit Fundstellen)

**1. `state.errors` als stringly-typed Mehrzweckkanal — grösste strukturelle Schuld.**
Echte Fehler, Advisory-Flags und Warnungen teilen sich eine `list[str]`; der Orchestrator
klassifiziert per Substring/Regex (`orchestrator.py:32,41-44,65-68`) Meldungen, die
`data_contract.py:255-284` und `code_generator.py:338,400-402` erzeugen. Eine umformulierte
Meldung bricht Review-Queue-Klassifikation drei Module weiter, ohne dass ein Test rot wird.

**2. Latenter HITL-Bug: `apply_human_decision` prunt per Substring** (`orchestrator.py:298-303`):
Owner-Zuweisung für Asset `customer` entfernt auch das ungelöste Flag für `customer_address`.

**3. LLM-Callpfad ungehärtet.** Kein `stop_reason`-Check: läuft der Modeler in `_MAX_TOKENS`
(8192), fällt der Aufruf still auf `{}` zurück (`dv2_modeler.py:96-98`) — ununterscheidbar von
"Modell fand nichts", ein Retry wird für `E_NO_HUBS` verbrannt. Kein Retry/Backoff bei
429/529; der CLI-`except Exception` (`cli.py:326`) schluckt den Stacktrace. Kein Prompt-Caching
trotz identischer System-Prompts über bis zu 3 Modeling-Retries (direkter Opus-Kostenhebel).

**4. Vier konkrete Validator-Lücken.** (a) Duplikat-Attribut *innerhalb* eines Satelliten
passiert unbemerkt (`validator.py:243-247`, Set-Semantik) → Generator emittiert doppelte
Payload-Spalte, Postgres bricht bei `dbt build`. (b) Eff-Sat-Datumsreihenfolge wird angenommen,
nicht geprüft: Generator nimmt `attributes[0]` als Start (`code_generator.py:240-241`); ein LLM
mit `["effective to", "effective from"]` erzeugt einen still invertierten Eff-Sat —
`effectivity_date_pair()` existiert bereits und könnte hier prüfen. (c) Hub-HK-Kollision bei
geteiltem `source_entity` ungeprüft (`code_generator.py:79-80`). (d) Gleicher BK + gleiche
Entität wird nicht geflaggt (`W_BK_COLLISION_RISK` nur bei *verschiedenen* Entitäten,
`validator.py:267-268`).

**5. Generierte ADRs desinformieren.** Der Caveat "specialised constructs need dedicated
AutomateDV macros not yet generated" (`adr_author.py:148-156`) ist seit nh_link/ma_sat/eff_sat
falsch — jedes generierte ADR für solche Modelle führt Reviewer in die Irre. Zudem koppelt
`_DEFAULT_ADR_DIR` (`adr_author.py:23`) an das Repo-Layout (bricht als Wheel-Installation) und
die ADR-Nummerierung ist nicht idempotent (Nummer aus Repo-Verzeichnis, geschrieben ins
Output-Verzeichnis → Kollisionen zwischen Läufen).

**6. Boilerplate und tote Artefakte.** Vier fast identische Anthropic-Client-Klassen (~40
Zeilen je, z. B. `requirements_parser.py:70-105` vs. `business_key_identifier.py:55-90`);
`tools/` ist leer trotz CLAUDE.md-Konvention; Prompt-Dateien der vier deterministischen Agenten
werden nie geladen; `Settings.langsmith_*`/`log_level` ungenutzt; Jinja2 als Dependency
deklariert, aber nicht verwendet; Renderer-Duplikat `cli.py:237-248` ↔ `orchestrator.py:167-179`;
kein einziges Logging-Statement in src (Observability nur über `state.decisions`/`errors`);
`checkpoints.sqlite` wächst ohne Pruning (`cli.py:110-111`).

**7. Doku-Drift.** CLAUDE.md/Spec sprechen von "10 Gates", der Validator hat 22 Issue-Codes
(14 E_, 8 W_). Die Docstring-Behauptung "interrupt() ist das erste Statement" stimmt nicht mehr
(`orchestrator.py:315-324` — heute harmlos, aber die schützende Invariante ist bereits falsch).

## Offene Punkte / bewusst zurückgestellt

Staging-Generator (grösster Produkt-Gap: Output ist ohne handgeschriebene `stg_*`-Modelle und
Projekt-Scaffolding kein lauffähiges dbt-Projekt), Source-Dialekt-Naming und
Business↔Source-Mapping (ADR-0008, Phase 2), DDL-/DB-Introspection (Phase 2/3), Business-Vault-
Assist und Mart-Scaffolding (Phase 3), UI (bewusst nach Pipeline-Stabilität). `eval/` ist leeres
Scaffolding — LangSmith ist deklariertes nächstes Milestone, aber nicht begonnen; für ein
LLM-Produkt mit Halluzinationsrisiko der wichtigste fehlende Qualitätsbaustein. Ferner offen aus
reality-test: Widerspruchs-Reconciliation (#1), typisierte Schema-Qualitätsgates (#4),
Multi-Rollen-Links (#5). Multi-Active-Sats/transactional Links im Demo bewusst offen.

## Optimierungspotenziale (priorisiert)

| P | Massnahme | Aufwand | Wirkung |
|---|---|---|---|
| 1 | Typisiertes `PipelineFlag`-Modell (severity, agent, asset, kind) statt `state.errors`-Strings; behebt zugleich Schwäche 1 und 2 | M | Hoch — Korrektheit + Entkopplung Orchestrator/Contracts/CLI |
| 2 | Generischer `forced_tool_call`-Helper mit `stop_reason`-Check und Backoff-Retry; ersetzt die 4 Client-Klassen (−~120 LOC) | M | Hoch — Zuverlässigkeit jedes LLM-Calls |
| 3 | Staging-Generator (`automate_dv.stage` + sources.yml + Projekt-Scaffolding aus vorhandener Metadata) | L | Höchste Produktwirkung — schliesst den "kein lauffähiges Projekt"-Gap; reine Templating-Arbeit, keine Forschung |
| 4 | Validator-Gates ergänzen: Eff-Sat-Datumsreihenfolge, Dup-Attribut-in-Sat, Hub-HK-Kollision, BK+Entität-Duplikat | S/M | Mittel — vier reale Korrektheitslöcher |
| 5 | `apply_human_decision` auf exaktes Asset-Matching umstellen | S | Mittel — echter HITL-Bug |
| 6 | ADR-Author: falschen Caveat entfernen, Nummerierung pro Output-Verzeichnis, Repo-Pfad-Kopplung lösen | S | Mittel — Glaubwürdigkeit der generierten Doku |
| 7 | Prompt-Caching (`cache_control` auf System-Block) + Retry-Feedback nur mit Errors statt vollen Issues | S | Mittel — direkter Kostenhebel, v. a. Opus |
| 8 | `ValidationIssue` (und ggf. `Decision`) als pydantic-Modelle statt `dict[str, Any]` | S | Mittel — Konventionstreue, entfernt Defensive-Parsing |
| 9 | Hygiene: Renderer zusammenführen, tote Prompts/`tools/`/ungenutzte Deps (Jinja2 oder nutzen) aufräumen, Logging + `--debug`-Flag, Checkpoint-Pruning; CLAUDE.md "10 Gates" korrigieren | S | Niedrig-mittel |
| 10 | Eval-Harness starten (LangSmith): zunächst die 2 Demo-Datensätze als Regressionssuite für die LLM-Agenten; plus Grössen-Guard/Chunking im requirements_parser | M | Strategisch — einziger Weg, LLM-Regressionen messbar zu machen |

## Empfohlene Reihenfolge

Erst härten, dann bauen: P1+P2 (typisierte Flags, LLM-Callpfad) als Batch vor neuen Features —
beide Schulden wachsen mit jedem weiteren Agenten. Danach P3 (Staging-Generator) als nächstes
Produktinkrement, flankiert von P4/P5 (Korrektheit) und P10 (Evals), bevor Phase-2-Themen
(Mapping, Introspection) beginnen.
