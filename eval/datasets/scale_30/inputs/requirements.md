# Data Vault requirements — synthetic enterprise landscape

This landscape spans 30 source tables across three systems: a legacy core system (VEKTRA), a CRM, and a peripheral system (AVIS). The business entities and their relationships to model are described below. The full physical schema (column names, types, comments) is supplied separately as the source schema; this document names the business concepts, not every physical table.

## Core business entities

- **Partner** — each partner is identified by a partner number. It is mastered in both the legacy core and the CRM, where it is known as 'ExternalPartnerNo'. We track partner name, date of birth, partner type for each partner.
- **Vertrag** — each vertrag is identified by a contract number. It is mastered in both the legacy core and the CRM, where it is known as 'ContractNo'. We track contract status, premium for each vertrag.
- **Police** — each police is identified by a policy number. It is mastered in both the legacy core and the CRM, where it is known as 'PolicyNo'. We track branch of insurance for each police.
- **Schaden** — each schaden is identified by a claim number. It is mastered in both the legacy core and the CRM, where it is known as 'ClaimNo'. We track loss date, reserve amount for each schaden.
- **Konto** — each konto is identified by a account number. We track iban, currency for each konto.
- **Produkt** — each produkt is identified by a product code. We track product name for each produkt.
- **Rechnung** — each rechnung is identified by a invoice number. We track invoice amount, due date for each rechnung.
- **Zahlung** — each zahlung is identified by a payment reference. We track payment amount for each zahlung.
- **Makler** — each makler is identified by a broker number. We track broker name for each makler.
- **Agentur** — each agentur is identified by a agent number. We track agency region for each agentur.
- **Deckung** — each deckung is identified by a coverage number. We track sum insured for each deckung.
- **Haushalt** — each haushalt is identified by a household number. We track postal code for each haushalt.
- **Fahrzeug** — each fahrzeug is identified by a vehicle number. We track license plate for each fahrzeug.
- **Tarif** — each tarif is identified by a tariff code. We track tariff group for each tarif.

## Further business entities

- **Objekt** — each objekt is identified by a objekt number.
- **Risiko** — each risiko is identified by a risiko number.
- **Beleg** — each beleg is identified by a beleg number.

## Relationships

- A partner relates to a partner over an active period (valid-from / valid-to); model this as a link with its effectivity.
- A partner relates to a contract over an active period (valid-from / valid-to); model this as a link with its effectivity.
- A contract relates to a policy over an active period (valid-from / valid-to); model this as a link with its effectivity.
- A contract relates to a claim over an active period (valid-from / valid-to); model this as a link with its effectivity.
- A policy relates to a product over an active period (valid-from / valid-to); model this as a link with its effectivity.
- A policy relates to a payment over an active period (valid-from / valid-to); model this as a link with its effectivity.
- A claim relates to a agent over an active period (valid-from / valid-to); model this as a link with its effectivity.

## Derived measures (out of raw-vault scope)

- **customer lifetime value** — derived KPI, computed in the mart — no source column.
- **loss ratio** — derived KPI (claims / premium) — computed downstream, not sourced.
- **broker commission plan** — maintained in a broker Excel list, out of the OLTP scope.
