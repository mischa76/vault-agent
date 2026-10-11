# Human-in-the-loop checkpoint

**Status:** requires sign-off — 10 decision(s), 0 disclosure(s).

## Decisions

### Contract owners to assign (block agreement)

- **Assign an owner for contract 'customer'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'account'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_
- **Assign an owner for contract 'account_customer'** — The agent never invents an owner; assign one before agreeing the contract. _(data_contract)_

### Review flags (advisory)

- **7× undetermined field type** — e.g. customer.date_of_birth, account.balance, … — review before agreeing _(data_contract)_
