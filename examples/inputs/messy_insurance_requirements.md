# Fachkonzept (Auszug) — Projekt "ATLAS-DWH": Partner- & Vertragsdaten-Integration

*Interne Vorlage v0.7 (Entwurf, teils noch in Abstimmung). Dieses Dokument ist bewusst so
gehalten, wie reale Lastenhefte ankommen — unvollständig, teils widersprüchlich, gemischt
fachlich/technisch. Es dient als Realitäts-Test für vault-agent (siehe docs/pre-mortem.md).*

## 1. Ausgangslage und Zielsetzung

Die Gesellschaft betreibt historisch gewachsene Systeme. Ziel ist eine integrierte, auditierbare
"Single Source of Truth" für eine 360°-Kundensicht, bessere Cross-Selling-Quoten und ein
revisionssicheres Reporting an die FINMA. Das DWH soll künftig auch Self-Service-BI ermöglichen.
Die Fachbereiche Vertrieb, Underwriting und Schaden haben unterschiedliche Sichten und Begriffe
auf "den Kunden" — das soll vereinheitlicht werden, ohne dass jemand seine gewohnten Auswertungen
verliert.

## 2. Quellsysteme (Auswahl)

- **VICTOR** (Legacy, IBM i / AS400): liefert nächtlich Flatfile-Exporte. Partner stehen in
  `PARTN_NR`, Verträge in `VTG_NR`. Felder sind teils kryptisch und nicht dokumentiert. VICTOR
  kennt keine echte Versionierung — es überschreibt.
- **CRM (Salesforce)**: Kunden als "Accounts" mit 18-stelliger `AccountId`. Zusätzlich gibt es
  eine "externe Kundennummer", die *eigentlich* der VICTOR-`PARTN_NR` entsprechen sollte —
  das Mapping ist aber nur für ca. 70% der Partner gepflegt.
- **ClaimsPro** (Schadensystem): Schadenfälle mit Schadennummer, referenzieren die Police über
  `Policy-No` (Format anders als VICTOR `VTG_NR`).
- **Vertriebs-Excellisten** der Makler: uneinheitlich, enthalten u.a. Maklercode und Provisionen.

> Hinweis Architektur: VICTOR und CRM beschreiben dieselben Partner unterschiedlich. Eine
> verbindliche Schlüssel-Harmonisierung existiert noch nicht (siehe offene Punkte).

## 3. Fachliche Anforderungen

3.1 Ein **Partner** kann eine **Privatperson** oder eine **Firma** sein. Privatpersonen werden —
sofern vorhanden — über die **AHV-Nummer** eindeutig identifiziert, Firmen über die **UID**. Nicht
für alle Partner liegen diese Nummern vor (Auslandsfälle, Altbestand). Intern vergibt VICTOR jedem
Partner zusätzlich eine technische ID (eine Art GUID).

3.2 Zu jedem Partner gehören die üblichen Stammdaten (Name, Adresse, Kontaktangaben etc.).
**Adressänderungen sind historisch nachvollziehbar** zu halten — man muss rekonstruieren können,
welche Adresse zu einem bestimmten Datum gültig war.

3.3 Ein **Vertrag** (Police) gehört einem **Versicherungsnehmer**. *(An anderer Stelle, Abschnitt
4, ist von Verbundverträgen mit mehreren beteiligten Partnern die Rede — das ist noch zu
konsolidieren.)* Ein Vertrag hat eine Vertragsnummer, eine Sparte, einen Status (offeriert, aktiv,
sistiert, storniert) und eine Prämie.

3.4 **Prämienanpassungen** werden versioniert; die zu einem Stichtag gültige Prämie ergibt sich aus
dem jeweiligen Anpassungsdatum.

3.5 **Schäden**: Zu einem Vertrag können mehrere Schadenfälle entstehen. Jeder Schadenfall hat ein
Meldedatum, einen Status und eine Schadensumme.

3.6 **Schadenzahlungen**: Aus einem Schadenfall erfolgen eine oder mehrere Zahlungen an einen
Begünstigten. Jede Zahlung hat Betrag, Währung, Valutadatum und eine Zahlungsreferenz.

3.7 Makler/Vermittler sind einem Vertrag zugeordnet (Vermittlerverhältnis); Provisionen sind pro
Vertrag und Vermittler auszuweisen.

## 4. Beteiligungen / Rollen (in Klärung)

Bei **Verbundverträgen** können mehrere Partner in unterschiedlichen Rollen beteiligt sein:
Versicherungsnehmer, versicherte Person, Prämienzahler, Begünstigter. Dieselbe Person kann mehrere
Rollen gleichzeitig innehaben. Die Rollenzuordnung kann sich über die Vertragslaufzeit ändern.

## 5. Nicht-funktionale Anforderungen / Compliance

- DSG/DSGVO: Datenminimierung; besonders schützenswerte Daten (Gesundheitsdaten in
  Schadenfällen) nur soweit nötig.
- Aufbewahrung 10 Jahre; Löschkonzept noch offen.
- Revisionssicherheit/Audit-Trail (FINMA).
- Nachtladefenster begrenzt; Mengengerüst ca. 2 Mio. Partner, 3,5 Mio. Verträge.

## 6. Offene Punkte / TODO

- Verbindliches Mapping VICTOR `PARTN_NR` ↔ CRM externe Kundennummer fehlt.
- Definition "aktiver Vertrag" fachlich noch nicht final.
- Begünstigten-Datenmodell (natürliche vs. juristische Personen, Bankverbindung) noch offen.
- Soll die technische VICTOR-ID als Schlüssel dienen oder nur als Hilfsmerkmal? (Diskussion offen.)
- Sparten-Katalog wird separat geliefert.
