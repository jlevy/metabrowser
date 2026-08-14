---
type: is
id: is-01kzzac20ctr8snmzgr65qh56c
title: "PR #40 review R7: share breakdown child limits with validator"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzzabe6f9r3fwtbd3w4tddqy
created_at: 2026-08-14T05:02:01.739Z
updated_at: 2026-08-14T05:25:17.576Z
closed_at: 2026-08-14T05:25:17.575Z
close_reason: "Fixed: wire validation reads the shared filename and remaining-type limit constants instead of hard-coded bounds."
---
PR #40 comment 5289663054, R7. wire_models.py hardcodes 20 rather than using the rollup fallback limits. Establish one source of truth and test limit drift.
