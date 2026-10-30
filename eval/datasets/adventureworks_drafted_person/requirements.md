<!-- Drafted deterministically from the AdventureWorks catalogue (Microsoft, MIT — see
NOTICE) by eval.adventureworks.draft_requirements: tables, descriptions, keys and foreign
keys as the catalogue states them. No analyst has read or written this. The C1 experiment,
2026-10-30. -->

# Requirements drafted from the source catalogue: person

**Area:** Person  
**Prepared by:** nobody — drafted from the catalogue  
**Status:** Draft, unreviewed

## 1. Purpose

The business needs to analyse what the person area of the operational system records. This document lists what that area records, as the system's own catalogue describes it: its tables, what identifies each, what each records, and how they refer to one another. It states nothing the catalogue does not.

## 2. Business entities in scope

| Concept | What the catalogue says it is |
|---|---|
| Address | Street address information for customers, employees, and vendors. |
| Address type | Types of addresses stored in the Address table. |
| Business entity | Source of the ID that connects vendors, customers, and employees with address and contact information. |
| Business entity address (a relationship) | Cross-reference table mapping customers, vendors, and employees to their addresses. |
| Business entity contact (a relationship) | Cross-reference table mapping stores, vendors, and employees to people |
| Contact type | Lookup table containing the types of business entity contacts. |
| Country region | Lookup table containing the ISO standard codes for countries and regions. |
| Email address | Where to send a person email. |
| Password (a kind of another concept) | One way hashed authentication information |
| Person (a kind of another concept) | Human beings involved with AdventureWorks: employees, customer contacts, and vendor contacts. |
| Person phone | Telephone number and type of a person. |
| Phone number type | Type of phone number of a person. |
| State province | State and province lookup table. |

## 3. Address

Street address information for customers, employees, and vendors.

- **REQ-001** The business must record every **address**.
- **REQ-002** Each address is identified by its **address id**.
- **REQ-003** The business must record the **address line1** of each address: First street address line.
- **REQ-004** The business must record the **address line2** of each address: Second street address line.
- **REQ-005** The business must record the **city** of each address: Name of the city.
- **REQ-006** The business must record the **postal code** of each address: Postal code for the street address.
- **REQ-007** The business must record the **spatial location** of each address: Latitude and longitude of this address.
- **REQ-008** Each address refers to one **state province** (by its state province id).
- **REQ-009** Each address carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 4. Address type

Types of addresses stored in the Address table.

- **REQ-010** The business must record every **address type**.
- **REQ-011** Each address type is identified by its **name**.
- **REQ-012** Each address type carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 5. Business entity

Source of the ID that connects vendors, customers, and employees with address and contact information.

- **REQ-013** The business must record every **business entity**.
- **REQ-014** Each business entity is identified by its **business entity id**.
- **REQ-015** Each business entity carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 6. Business entity address

Cross-reference table mapping customers, vendors, and employees to their addresses.

- **REQ-016** The business must record which **address**, **address type**, **business entity** are related, as a **business entity address**.
- **REQ-017** Each business entity address is identified by the combination of **business entity id**, **address id**, **address type id**.
- **REQ-018** Each business entity address carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 7. Business entity contact

Cross-reference table mapping stores, vendors, and employees to people

- **REQ-019** The business must record which **person**, **contact type**, **business entity** are related, as a **business entity contact**.
- **REQ-020** Each business entity contact is identified by the combination of **business entity id**, **person id**, **contact type id**.
- **REQ-021** Each business entity contact carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 8. Contact type

Lookup table containing the types of business entity contacts.

- **REQ-022** The business must record every **contact type**.
- **REQ-023** Each contact type is identified by its **name**.
- **REQ-024** Each contact type carries a last-changed timestamp.

## 9. Country region

Lookup table containing the ISO standard codes for countries and regions.

- **REQ-025** The business must record every **country region**.
- **REQ-026** Each country region is identified by its **name**.
- **REQ-027** Each country region carries a last-changed timestamp.

## 10. Email address

Where to send a person email.

- **REQ-028** The business must record every **email address**.
- **REQ-029** Each email address is identified by the combination of **business entity id**, **email address id**.
- **REQ-030** The business must record the **email address** of each email address: E-mail address for the person.
- **REQ-031** Each email address refers to one **person** (by its business entity id).
- **REQ-032** Each email address carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 11. Password

One way hashed authentication information

- **REQ-033** The business must record every **password**. Every password is a **person** and is identified by the same **business entity id**.
- **REQ-034** The business must record the **password hash** of each password: Password for the e-mail account.
- **REQ-035** The business must record the **password salt** of each password: Random value concatenated with the password string before the password is hashed.
- **REQ-036** Each password carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 12. Person

Human beings involved with AdventureWorks: employees, customer contacts, and vendor contacts.

- **REQ-037** The business must record every **person**. Every person is a **business entity** and is identified by the same **business entity id**.
- **REQ-038** The business must record the **person type** of each person: Primary type of person: SC = Store Contact, IN = Individual (retail) customer, SP = Sales person, EM = Employee (non-sales), VC = Vendor contact, GC = General contact
- **REQ-039** The business must record the **name style** of each person: 0 = The data in FirstName and LastName are stored in western style (first name, last name) order.  1 = Eastern style (last name, first name) order.
- **REQ-040** The business must record the **title** of each person: A courtesy title. For example, Mr. or Ms.
- **REQ-041** The business must record the **first name** of each person: First name of the person.
- **REQ-042** The business must record the **middle name** of each person: Middle name or middle initial of the person.
- **REQ-043** The business must record the **last name** of each person: Last name of the person.
- **REQ-044** The business must record the **suffix** of each person: Surname suffix. For example, Sr. or Jr.
- **REQ-045** The business must record the **email promotion** of each person: 0 = Contact does not wish to receive e-mail promotions, 1 = Contact does wish to receive e-mail promotions from AdventureWorks, 2 = Contact does wish to receive e-mail promotions from AdventureWorks and selected partners.
- **REQ-046** The business must record the **additional contact info** of each person: Additional contact information about the person stored in xml format.
- **REQ-047** The business must record the **demographics** of each person: Personal information such as hobbies, and income collected from online shoppers. Used for sales analysis.
- **REQ-048** Each person carries a last-changed timestamp and a technical row identifier, which is not a business key.

## 13. Person phone

Telephone number and type of a person.

- **REQ-049** The business must record every **person phone**.
- **REQ-050** Each person phone is identified by the combination of **business entity id**, **phone number**, **phone number type id**.
- **REQ-051** Each person phone refers to one **person** (by its business entity id).
- **REQ-052** Each person phone refers to one **phone number type** (by its phone number type id).
- **REQ-053** Each person phone carries a last-changed timestamp.

## 14. Phone number type

Type of phone number of a person.

- **REQ-054** The business must record every **phone number type**.
- **REQ-055** Each phone number type is identified by its **phone number type id**.
- **REQ-056** The business must record the **name** of each phone number type: Name of the telephone number type
- **REQ-057** Each phone number type carries a last-changed timestamp.

## 15. State province

State and province lookup table.

- **REQ-058** The business must record every **state province**.
- **REQ-059** Each state province is identified by its **name**.
- **REQ-060** The business must record the **state province code** of each state province: ISO standard state or province code.
- **REQ-061** The business must record the **is only state province flag** of each state province: 0 = StateProvinceCode exists. 1 = StateProvinceCode unavailable, using CountryRegionCode.
- **REQ-062** Each state province refers to one **country region** (by its country region code).
- **REQ-063** Each state province refers to one **sales territory** (by its territory id).
- **REQ-064** Each state province carries a last-changed timestamp and a technical row identifier, which is not a business key.
