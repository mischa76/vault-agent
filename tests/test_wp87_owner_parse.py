"""WP87 — a bare email at sign-off is the owner's address, its local part the name (spec §2.1).
Committed before the change, failing for the bare address."""
from __future__ import annotations

from vault_agent.cli import _parse_owner


def test_name_and_address_as_before() -> None:
    assert _parse_owner("customer=John Doe <john.doe@acme.com>") == (
        "customer", {"name": "John Doe", "email": "john.doe@acme.com"})


def test_a_bare_address_is_the_email_and_its_local_part_the_name() -> None:
    assert _parse_owner("customer=john.doe@acme.com") == (
        "customer", {"name": "john.doe", "email": "john.doe@acme.com"})


def test_a_plain_name_stays_a_name_without_email() -> None:
    assert _parse_owner("customer=Data Team") == ("customer", {"name": "Data Team", "email": None})
