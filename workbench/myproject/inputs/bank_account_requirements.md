# Bank Account Domain – Toy Requirements

A customer can open one or more accounts. Each account belongs to exactly one customer
at any point in time but ownership can be transferred. An account has a unique account
number (issued by the bank), a current balance, and a status (active, frozen, closed).

A customer is identified by their national customer ID. The bank also assigns its own
customer reference. The customer has a name, a date of birth, and one or more addresses.

Transactions move funds between accounts. Every transaction has an amount, a timestamp,
a counterparty account, and a reference text.

Compliance requires that all balance changes are auditable: who, what, when, why.
