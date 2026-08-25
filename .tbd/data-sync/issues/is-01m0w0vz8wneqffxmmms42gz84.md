---
type: is
id: is-01m0w0vz8wneqffxmmms42gz84
title: "PR #74 scope audit S7: make refresh completion observable without transactional overclaim"
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:33:55.994Z
updated_at: 2026-08-25T08:33:55.994Z
---
The architecture promises one atomic provider refresh and one resulting cursor, but RefreshReceipt carries no observation boundary and the Python provider commits valid observations separately. Define the minimal useful guarantee: one bounded refresh call returns a terminal EngineVersion after all accepted observations have been incorporated; do not require filesystem hints to become a fictitious transaction. Update contract, coordinator/provider tests, docs, and the FDU adoption gate.
