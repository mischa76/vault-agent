---
title: "Why Data Vault 2.0 Is Ready for Agentic AI"
subtitle: "The most rule-bound corner of data warehousing is also the one best suited to a team of agents."
author: Mischa Eismann
status: DRAFT
target_length: ~1200 words
audience: DACH data architects, consultants, and technical decision-makers
date: 2026-06
canonical: https://eismann.consulting
---

# Why Data Vault 2.0 Is Ready for Agentic AI

Ask any architect who has stood up a Data Vault from scratch what the first two weeks
actually look like, and you will not hear stories of elegant design. You will hear about
reading the same requirements document for the fifth time, arguing over whether the customer
number or the contract number is the real business key, and hand-cranking hubs, links, and
satellites that all look almost — but not quite — the same. The interesting decisions are
real, but they are surrounded by hours of disciplined, repetitive translation work.

That combination — high rigor, low creativity, heavy repetition — is unusual. And it is
exactly the shape of problem that agentic AI is unexpectedly good at.

## The bottleneck is human, and it is the boring part

Data Vault 2.0 earned its place in regulated enterprises — banks, insurers, pharma, the
kind of organizations that fill the Swiss and DACH data landscape — because it is built for
auditability, full historization, and resilience to change. Those are not nice-to-haves
when a regulator can ask what a record looked like on a given Tuesday three years ago.

But the methodology pays for those guarantees with structure. A hub is one row per unique
business key, with a hash key, a load timestamp, and a record source. A link models a
relationship between hubs with the same skeletal columns. A satellite carries the
descriptive attributes that change over time, tracked with a hash diff. The rules are
clear, well-documented, and — crucially — *the same every time*.

So the bottleneck at the start of a project is rarely a shortage of good ideas. It is a
shortage of senior hours to do work that is too rule-bound to be interesting and too
judgment-laden to hand to a junior without close review. Weeks of an architect's time go
into modeling that, in retrospect, mostly followed a script.

## Why this problem fits agents specifically

A lot of "AI for X" pitches fail because the underlying task is fuzzy, unverifiable, or has
no ground truth. Data Vault modeling is the opposite on all three counts, and that is what
makes it a strong candidate rather than just another demo.

It **decomposes cleanly.** Parsing requirements, scoring business-key candidates, generating
the hub/link/satellite structure, emitting load code, writing contracts, validating the
result — these are distinct steps with distinct inputs and outputs. That is precisely the
boundary you want when you assign each step to a specialized agent instead of asking one
model to do everything in a single prompt. Each agent can be small, focused, and individually
testable.

It is **rule-checkable.** Unlike open-ended generation, a Data Vault model is either compliant
or it is not. A business key should be stable, globally unique within its universe, recognized
by the business, and not nullable. A satellite either has its hash diff or it doesn't. Because
the rules are explicit, a validator agent can mechanically check the output of the creative
ones — which means the system can catch and correct its own mistakes before a human ever sees
them.

It is **decision-heavy in a documentable way.** Every Data Vault project quietly accumulates
dozens of small judgment calls: why this key and not that one, why this satellite was split,
why a link was modeled as a transaction. Today those decisions live in someone's head and
evaporate when they leave the project. They are exactly the kind of reasoning a system can be
made to externalize — as Architecture Decision Records — turning tribal knowledge into a
durable artifact.

## "But AI hallucinates and Data Vault is strict"

This is the right objection, and it is the one I take most seriously. A model that
confidently invents a business key is worse than useless in a regulated warehouse. The answer
is not to trust the model more; it is to build the system so that trust is not required.

Four design choices do most of that work.

First, **the rules live in code, not in prompts.** The methodology — what makes a valid hub,
what disqualifies a business-key candidate — is enforced by deterministic validators, not
politely suggested to a language model and hoped for. The agents propose; the rules dispose.

Second, **code generation goes through an established engine.** Rather than asking a model to
write dbt SQL from a blank page, the system drives AutomateDV, the open-source dbt package
that already encodes correct Data Vault loading patterns. The model decides *what* to build;
a battle-tested package decides *how* it is rendered. That removes an entire category of
hallucinated SQL.

Third, **a validator sits in the loop.** Generated artifacts are checked for compliance, and
violations the system can fix are fixed automatically; the ones it cannot are escalated.

Fourth, **humans stay in the loop where it matters.** When two business-key candidates score
within a hair of each other, or the validator finds something it cannot resolve, the system
stops and asks. It does not guess on the decisions that are expensive to get wrong.

The output is never a no-code black box. It is a reviewed dbt project in git, with the
reasoning captured alongside it. An architect can read every line and every decision — they
just did not have to type all of them.

## What changes for the architect

The fear with any automation in a skilled field is replacement. That is not what is on offer
here, and pretending otherwise would be dishonest. A system like this does not have taste. It
does not know that this particular insurer treats policy and claim as the same business object
for historical reasons, or that the source system everyone trusts is quietly wrong about
effective dates. That judgment is the job, and it stays with the human.

What changes is the ratio. Instead of spending the first weeks of a project translating
requirements into boilerplate, the architect spends them on the decisions that actually
require an architect — and reviews, rather than authors, the rest. The repetitive 80% gets
compressed; the creative 20% gets more room. That is a better job, not a smaller one.

## Building it in the open

This is not a thought experiment for me. I am building exactly this system — a multi-agent
pipeline that takes business requirements and source schemas and produces a compliant Data
Vault 2.1 model, AutomateDV-backed dbt code, and the data contracts and decision records to
go with it — and I am doing it publicly, grounded in the DV2.1 methodology, Roelant Vos's
DSAF, and proper requirements-engineering practice rather than improvisation.

The interesting question was never whether a model can generate a hub. It obviously can. The
interesting question is whether you can wrap that capability in enough structure — rules in
code, deterministic generation, validation, human checkpoints, traceable decisions — that the
result is something a regulated enterprise would actually trust. I think you can. The next
posts will show the parts as they come together.

If you work in this space and have opinions — especially the skeptical kind — I want to hear
them.

---

*Mischa Eismann is a hybrid technical/business data architect (CDVP², 20+ years in ICT) at
[eismann.consulting](https://eismann.consulting), building Vault-Agent in the open.*
