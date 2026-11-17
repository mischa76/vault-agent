---
type: spec
status: not-measured
updated: 2026-11-17
---

# WP144 — A proposed bridge is one decision per link pair and shared hub; the ends are chosen when building (C53, option (a))

Status: **Approved and in progress** (2026-11-17, on the owner's go of that day: all open workbench-usability
candidates) · Owner: Mischa Eismann · Author: Claude. Candidate C53, option (a) — set aside on 2026-11-08 „for
later, with the checkpoint controls" (WP122 built (b)); those controls are WP142. Last of four packages.
**Unlike the other three this one is not only the page:** it changes how many decisions a run with the
Business Vault on raises.

## 1 What is wrong

`propose_bridge_paths` (WP115 §2.2) emits one path per pair of links citing one requirement and sharing a
hub, per start participation of the first and per exit of the second — and every path is its own review
decision (`bridge_proposal_flags`). The variants of one pair differ only in their ends. Counted at zero cost
on the stored second chain of 2026-11-15 (the Business Vault was off there; this is what the proposer offers
with it on, each step with the earlier steps' paths declined, as WP122 carries them): **174 paths over five
steps (1, 8, 6, 10, 149) in 22 link pairs (1, 2, 4, 3, 12)**, the largest pair with 28 variants. The
twenty-fifth chain's count of 2026-11-08 (49 paths, 25 pairs) cannot be measured again: its saved models are
not on this machine.

## 2 The rules

1. **The group.** A proposed path `start,first_link,shared_hub[:role],second_link,end` belongs to the group
   `first_link+second_link@shared_hub` (`business_vault_generator.bridge_group`); a path of any other shape —
   one an operator named — is a group of its own. The proposer, the path language and what is stored per
   path (`BridgeProposal`, its ratification, `metadata/bridge_decisions.yml`) do not change.
2. **One decision per group.** `bridge_proposal_flags` raises one `bridge_proposed` flag per group that
   still has an unanswered path — its asset is the group, its message names the pair, the hub and every
   pending path. WP115's rule „one decision per proposal" is superseded by this.
3. **Answering.** As before by path: `--bridge PATH` builds one, `--no-bridge PATH` declines one, and at
   `--accept` every unanswered path is declined. So a group is declined by leaving it, and built by naming
   the path whose ends are wanted — more than one where two are wanted. A group's flag goes when none of its
   paths is unanswered.
4. **The prompt** (`resume` in a terminal) asks once per group — build a bridge over the pair? — default no,
   and on yes which path, by number, where there are several.
5. **The page.** The checkpoint API's `bridges` entries carry `group`, `links` and `hub`; the Review
   perspective shows one card per group with WP142's control, `[ Decline | Build ]`, and — once „Build" is
   chosen and the group has several paths — a list to choose the path from. One path per group from the
   page; a second through the CLI.

**Output-changing for a run with the Business Vault on:** fewer `bridge_proposed` decisions — the review
queue, `review-queue.md`, the decision count the eval harness records. A chain with PIT on (the twenty-fifth)
is not comparable in its decision count with one after this change. A run without the Business Vault
proposes no bridge and changes in nothing; no byte-identity fixture moves.

## 3 Not built

- C53's (c) and (d): proposing only where the requirement names both ends, or counting proposals as
  disclosures.
- No pruning of variants: every path the proposer found can still be built.
- A group answer as a handle of its own (`--no-bridge <group>`): leaving a group declines it.

## 4 Acceptance (committed red)

`tests/test_wp144_bridge_groups.py`, `Review.test.tsx`:
- **G1** `bridge_group`: the pair and the hub, the shared hub's role ignored; an operator's path is its own.
- **G2** three groups over five paths raise three flags, in order, each naming its paths; a group with one
  path answered keeps its flag for the other; a group fully answered raises none.
- **G3** the code generator with the Business Vault on: five proposals stored, three decisions in the
  review queue.
- **G4** (pin, green before and after) building one path of a group and accepting: that path accepted, its
  sibling declined, no `bridge_proposed` flag left, the declines carried as WP122 carries them.
- **G5** the pending list for the page carries `group`, `links`, `hub`.
- **G6** the prompt asks once per group and, on yes, for the path; the answers are per path.
- **G7** (Vitest) one card per group; „Build" on a group with two paths offers both, the first chosen;
  the decision sends the chosen path `true` and its sibling `false`; a group left alone sends `false` for
  every path.
- **G8** WP115's and WP122's guards green; one assertion of WP115's updated deliberately (it pinned one flag
  per path).

## 5 Pre-registration

- **P1** G1–G3, G5–G7 red before, green after; G4 green on both; G8. Suite with no key reachable, ruff, bare
  mypy, `tsc`, Vitest, the build, UI coverage.
- **P2** (zero cost) the stored second chain of 2026-11-15 through the real proposer and the real flags, each
  step with the earlier steps' paths declined: **22 decisions where there were 174** (1, 2, 4, 3, 12).
- **P3** a sign-off with three groups over five paths in a real Chromium on the canned stub state: three
  cards, the decision count 4 (three and the open owner) where WP142's walk showed 6; one built with its
  second path chosen — `resume … --bridge <that path>` recorded with `--no-bridge` for the others.
- **Not measured:** a live chain with the Business Vault on; whether one decision per pair is the right
  grain for the owner — C53's (c) would cut further.

## 6 Measured (2026-11-17)

- **P1 held.** The Python guards red by import at `3d03c98`; run once against the old code with the two
  missing names stubbed, seven failed for their own reason and the fixture check and the pin G4 passed. Two
  Vitest cases red. With the change: all green, WP115's and WP122's guards green (one WP115 assertion updated
  in the red commit). Suite 1876 passed / 3 skipped with no key reachable, ruff, bare mypy, `tsc`, Vitest 61,
  the build, `vault_agent.ui` coverage 95 %. No byte-identity fixture changed.
- **P2 held.** The stored second chain of 2026-11-15 through the real proposer and the real flags, each
  step with the earlier steps' paths declined: **22 decisions where there were 174** — per step 1, 2, 4, 3,
  12 against 1, 8, 6, 10, 149; the largest decision carries 28 paths.
- **P3 held.** A real Chromium on the canned stub state: three cards under „Bridges", the sign-off's count
  4 decisions (WP142's walk on the same state: 6); the pair with two paths set to build offers both, the
  first chosen; with the second chosen and the owner filled the run recorded `resume … --bridge
  hub_branch,link_account_branch,hub_account,link_transfer,hub_account:counterparty` and `--no-bridge` for
  the four others, finished, and wrote those four to `metadata/bridge_decisions.yml`.
- **Looked like a defect, was not:** the first screenshot showed „Decline" still filled after „Build" was
  chosen. The control fades between its states; read 400 ms later the colours are the chosen one's
  (`aria-checked` was right at once).
- **Beside the spec:** the Review perspective's group list is computed per render, not memoised — it sits
  below the perspective's early returns, where a hook may not stand.
- **Not measured.** A live chain with the Business Vault on; the prompt in a real terminal (the guard
  scripts the prompter); a pair with 28 paths on the page — the list holds them, nobody has read it.
