---
type: is
id: is-01m1d3qscgv75446y3x56tyhbj
title: Add a provider conformance case for navigation tally row shape
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-23-pluggable-inventory-engine.md
labels: []
dependencies: []
parent_id: is-01m0r7eg6f4a4xee33ryv8sjfs
created_at: 2026-08-31T23:51:09.967Z
updated_at: 2026-11-14T18:46:06.482Z
---
test_provider_semantic_digest, a registered conformance case (tests/test_inventory_provider_contract.py:113), already pins the rollup payload for every provider factory: it asserts the top-level keys and runs validate_rollup_result (lines 1131-1137). The navigation payload gets only a key-set check (lines 1138-1147). Nothing checks the arity, element order or types of its extensions, canonical_extensions, type_families, type_presets and recency_tallies rows, which are list[list[object]] (see mb-gwlw), so a second provider could swap two columns of a tally row and pass every conformance case.

Add a factory-parametrized case that validates each navigation tally row against a fixed fixture tree (a validator beside validate_extension_tallies in wire_models.py, or the contract's own row types once mb-gwlw lands). Register it in PROVIDER_CONFORMANCE_TESTS and in the table in docs/project/architecture/arch-inventory-provider.md, which test_architecture_document_registers_every_provider_conformance_case requires.
