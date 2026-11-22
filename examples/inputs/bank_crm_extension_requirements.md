# CRM integration — extension of the existing customer/account vault

The bank already operates a Raw Vault covering customers, accounts and account ownership,
loaded from the core banking system. This document describes the **next increment**: the
marketing CRM is to be integrated into the same vault. Nothing about the existing structures
may change — they carry live history.

## Scope of this increment

### CRM as a second source for the customer

REQ-101. The CRM holds its own record of every customer. A CRM contact carries the same
national customer ID the core banking system uses, so a customer known to both systems is
one and the same business object, not two.

REQ-102. The CRM record carries information the core system does not: the customer's
marketing segment, their preferred contact channel, and whether they have opted out of
marketing communication. This information belongs to the customer, but it is CRM data — the
core system will never supply it.

### Campaigns

REQ-103. Marketing runs campaigns. A campaign is identified by its campaign code and has a
name, a start date and an end date.

REQ-104. A customer can be targeted by many campaigns, and a campaign targets many
customers. For each targeting we record when the customer was enrolled and, where
applicable, when they responded.

REQ-105. A campaign is owned by exactly one responsible marketing manager, identified by
their employee number. Reporting must be able to attribute campaign results to the manager
who ran them.

## Constraints

REQ-106. The existing hubs, links and satellites must remain exactly as they are. This
increment adds to the vault; it does not reshape it. In particular the core banking system
remains a source of customer records — the CRM joins it, it does not replace it.

REQ-107. Marketing attributes must be historised separately from the attributes the core
system supplies, so that a reload of either system cannot disturb the other's history.
