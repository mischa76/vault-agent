# Vault-Agent — Architektur- & Implementierungs-Review

**Datum:** 2026-06-13
**Umfang:** `src/vault_agent/**`, `tests/**`, `pyproject.toml`, Prompts und Regeln.
**Methode:** Statisches Code-Studium. `ruff`, `mypy` und `pytest` konnten in dieser Session
nicht ausgeführt werden (die Sandbox kann den WSL-UNC-Pfad nicht mounten) — die Befunde sind
nicht durch einen Testlauf gegengeprüft. Empfehlung: in CI verifizieren.

---

## Gesamturteil

Die Architektur ist sauber und entspricht dem in `CLAUDE.md` formulierten Anspruch. Der
LangGraph-Graph ist bewusst dünn, die Geschäftslogik liegt in den Agenten, die DV2.0-Regeln
in reinem Python (`rules/dv2_rules.py`), die Prompts als `.md`. Die Trennung zwischen
LLM-getriebenen Agenten (parser, business_key, modeler) und deterministischen Agenten
(code_generator, validator, adr_author) ist konsequent und gut begründet — sie macht
Codegenerierung und Validierung reproduzierbar und halluzinationsfrei.

Drei Muster sind besonders gelungen: (1) die durchgängige Dependency-Injection über
`Protocol`-Extraktoren, wodurch jeder LLM-Agent ohne API-Key testbar ist; (2) Forced
Tool-Use mit aus Pydantic abgeleiteten Schemata, sodass strukturierte Ausgaben ohne Ad-hoc-
Parsing zurück in die Modelle validieren; (3) Defense-in-Depth, bei der der Validator
strukturelle Invarianten unabhängig nachprüft, die Modeler und Generator bereits durchsetzen.

Die Hauptschwäche ist eine **echte Korrektheitslücke bei der Effectivity-Satellite-Generierung**
(siehe H-1): Der `driving_key`, den Modeler, Validator, Prompt und ADR sorgfältig
behandeln, wird vom Code-Generator ignoriert. Daneben gibt es einen ungültigen Modellnamen
in der Config und einige Roadmap-Lücken (keine Nutzung von `source_schemas`, kein
PDF/DOCX-Eingabepfad).

---

## Befunde nach Priorität

| # | Schwere | Bereich | Befund |
|---|---------|---------|--------|
| H-1 | **Hoch** | code_generator | Effectivity-Sat: `driving_key` wird ignoriert, `src_dfk` = erster verbundener Hub |
| H-2 | Mittel | config | `heavy_model = "claude-opus-4-6"` ist kein gültiger Modellstring → Modeler-Runs schlagen fehl |
| M-1 | Mittel | requirements_parser | Kein PDF/DOCX-Eingabepfad, obwohl Quelldokumente lt. Charter `.docx`/`.pdf` sind |
| M-2 | Mittel | state/pipeline | `source_schemas` wird von keinem Agenten gelesen; Modell entsteht rein aus Prosa |
| L-1 | Niedrig | graph | Retry-Cap koppelt an das Audit-Log (`decisions`) statt an einen expliziten Zähler |
| L-2 | Niedrig | code_generator | `_to_column` kann zwei Labels auf dieselbe Spalte kollabieren (keine Kollisionserkennung) |
| L-3 | Niedrig | config | `Settings()` beim Import → ohne `ANTHROPIC_API_KEY` crasht jeder direkte Import von `config` |
| L-4 | Niedrig | dv2_modeler | Draft-ADR-Fragmente akkumulieren über Retries in `state.adrs` (nur im Abbruchfall sichtbar) |
| L-5 | Niedrig | tests | Der eff_sat-Test zementiert das fehlerhafte Verhalten aus H-1 (bleibt grün, ist aber falsch) |

---

## Details

### H-1 — Effectivity-Satellite ignoriert den Driving Key (Korrektheit)

`_render_eff_sat` wählt den Driving Foreign Key fest als `hub_fks[0]` — also den *ersten*
verbundenen Hub — und alle übrigen als `src_sfk`:

```python
driving_fk = hub_fks[0]
secondary_fk = hub_fks[1:]
```

`link.driving_key` wird beim Rendern nie gelesen. Das ist inkonsistent mit dem Rest des
Systems, das den Driving Key sehr ernst nimmt: Der Validator erzwingt seine Existenz
(`E_EFFSAT_NO_DRIVING_KEY`), der Modeler-Prompt erklärt ausführlich, dass der Driving Key
die „one at a time"-Seite ist (z. B. der Mitarbeiter-Hub bei „ein Mitarbeiter hat einen
Manager zur Zeit"), und der ADR weist ihn aus. Wenn der Modeler `connected_hubs` in einer
Reihenfolge ausgibt, in der der Driving-Hub nicht an erster Stelle steht, dann datet die
generierte Effectivity-Satellite nach dem **falschen** Schlüssel ab — ein semantisch
falsches Data-Vault-Konstrukt, das die Validierung passiert.

Empfehlung: `link.driving_key` in `_render_eff_sat` durchreichen und `src_dfk`/`src_sfk`
daraus ableiten (Driving = Hashkeys der Hubs in `driving_key`, Secondary = Rest). Den Test
`test_effectivity_satellite_generates_on_link` entsprechend auf Driving-Key-Auswahl
umstellen (siehe L-5).

### H-2 — Ungültiger Heavy-Model-String

```python
heavy_model: str = "claude-opus-4-6"
```

Es gibt kein Modell `claude-opus-4-6` (aktuell ist es `claude-opus-4-8`). Der
`Dv2ModelerAgent` nutzt per Default `settings.heavy_model`, d. h. ein echter Pipeline-Lauf
des wichtigsten Reasoning-Schritts würde mit einem 404/Model-not-found scheitern.
`primary_model = "claude-sonnet-4-6"` ist gültig. Bitte den Heavy-Model-String korrigieren
und idealerweise beide Werte gegen die API verifizieren.

### M-1 — Kein PDF/DOCX-Eingabepfad

`RequirementsParserAgent._read_document` macht ausschließlich `path.read_text(...)`. `pypdf`
ist zwar Dependency, wird aber nicht genutzt; ein PDF/DOCX würde als Text-Müll gelesen. Die
CLI schränkt die Eingabe im Hilfetext auf „markdown/text" ein — das ist konsistent, steht
aber im Widerspruch zum Projektziel (Quelldokumente sind laut Charter `.docx`/`.pdf`).
Empfehlung: einen kleinen, dateityp-dispatchenden Reader (md/txt direkt, pdf via pypdf,
docx via python-docx) einziehen, bevor reale Lastenhefte verarbeitet werden.

### M-2 — `source_schemas` ungenutzt

`VaultAgentState.source_schemas` existiert, wird aber von keinem Agenten konsumiert. Business
Keys und Satelliten-Attribute werden allein aus dem Anforderungstext „erfunden", nicht gegen
reale Quellspalten validiert. Für DACH-DWH-Landschaften ist das Abgleichen gegen ein
tatsächliches Quellschema (Spalten existieren, BK ist not-null/unique in der Quelle) ein
zentraler Mehrwert. Sinnvoller Roadmap-Punkt — evtl. ein eigener „schema_grounding"-Schritt
zwischen business_key_identifier und dv2_modeler.

### L-1 — Retry-Cap an Audit-Log gekoppelt

`route_after_validation` zählt `decisions` mit `agent == "dv2_modeler"`, um den Retry-Cap
durchzusetzen. Das koppelt Kontrollfluss an das Logging: Ändert jemand, wie/ob der Modeler
seine Entscheidung protokolliert, bricht der Loop-Schutz still. Robuster wäre ein expliziter
`modeling_attempts: int` im State, den der Modeler inkrementiert.

### L-2 — Mögliche Spaltenkollision in `_to_column`

`_to_column` normalisiert über `[^0-9a-zA-Z]+ → _` und UPPER. „customer-id" und „customer id"
ergeben beide `CUSTOMER_ID`. Es gibt keine Kollisionserkennung auf generierten Spaltennamen.
Bei sauberen Inputs unkritisch, aber bei realen Lastenheften ein potenzieller stiller
Fehler. Eine Warnung im Generator bei kollidierenden Normalisierungen wäre billig.

### L-3 — `Settings()` beim Modulimport

`settings = Settings()` läuft beim Import von `config.py` und verlangt `anthropic_api_key`
ohne Default. Die „kein API-Key nötig"-Eigenschaft hält nur, weil `config` ausschließlich
*lazy* (im Extractor-`__init__`) importiert wird. Ein direkter `import vault_agent.config`
ohne gesetzten Key crasht jedoch hart. Erwäge einen lazy `get_settings()`-Zugriff oder eine
klarere Fehlermeldung.

### L-4 — Akkumulierende Draft-ADRs

Der Modeler hängt bei *jedem* Lauf ein Draft-ADR-Fragment an `state.adrs`. Auf dem Happy
Path setzt `adr_author` `state.adrs = [adr]` und überschreibt sie. Wird der Retry-Cap aber
erreicht (Route → `END`), bleiben N Fragmente liegen. Harmlos, aber unsauber — die
Fragmente vor dem Re-Modeling verwerfen oder gar nicht erst sammeln.

### L-5 — Test friert den H-1-Bug ein

`test_effectivity_satellite_generates_on_link` assertet explizit
`src_dfk = "ACCOUNT_HK"  # driving = first connected hub`. Der Test ist grün, kodiert aber
das falsche Verhalten. Nach Fix von H-1 muss dieser Test auf die Driving-Key-basierte Auswahl
umgestellt werden — sonst maskiert er die Korrektur.

---

## Was gut ist (bewusst beibehalten)

Die deterministischen Agenten (code_generator, validator, adr_author) ohne LLM sind die
richtige Designentscheidung und sauber umgesetzt. Der Validator ist als unabhängiges Gate mit
klaren `E_`/`W_`-Codes strukturiert und prüft auch konstruktübergreifend (Grain-Redundanz,
Attribut-Overlap, BK-Kollision) — das ist methodisch stark. Die Regeln in `dv2_rules.py`
treffen den Linstedt/Olschimke-Kanon gut (ein Hub pro BK, Links ohne Beschreibungsattribute,
Satelliten-Split-Achsen, Unit of Work, Collision Code), und die bewusste Abgrenzung der
Vos-Revisionen als „ADR-gated, nie stiller Default" zeigt gute Methoden-Disziplin. Die
Testabdeckung über alle Agenten, Graph und CLI ist breit; die Stubs (`data_contract`,
`orchestrator`) sind ehrlich als `NotImplementedError` markiert und konsistent mit dem
dokumentierten Milestone.

---

## Empfohlene Reihenfolge

1. **H-1** beheben (Driving-Key-Durchreichung) und **L-5** mitziehen — größtes
   Korrektheitsrisiko, betrifft den DV-Kern.
2. **H-2** Modellstring korrigieren — sonst läuft kein echter Modeler-Schritt.
3. **M-1** Mehrformat-Reader, **M-2** Schema-Grounding — schalten reale Lastenhefte frei.
4. **L-1 bis L-4** als Aufräum-/Härtungsarbeiten in einem späteren PR.
