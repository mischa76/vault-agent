# Health Insurance Domain – Toy Requirements

An insured person holds one or more health insurance policies. Each policy belongs to
exactly one insured person, but a policy can be transferred to another person within the
same household. A policy has a unique policy number (issued by the insurer), an
effective-from and effective-to date, a coverage level (basic, supplementary), and a status
(applied, active, suspended, terminated).

An insured person is identified by their national insured number. The insurer also assigns
its own member number. An insured person has a name, a date of birth, and one or more
contact addresses.

Premiums are paid against a policy. Each premium payment has an amount, a payment date, and
a payment method.

A claim is submitted against a policy. Every claim has a claim number, a treatment date, a
submission date, a billed amount, and a reimbursed amount.

A claim refers to exactly one healthcare provider. A provider is identified by their
provider registration number and has a name and a medical specialty.

Regulators require that every change to a policy's coverage level and status is auditable:
who changed it, what changed, when, and why.
