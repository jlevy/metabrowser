---
type: is
id: is-01kzzac20ctr8snmzgr65qh56c
title: "PR #40 review R7: share breakdown child limits with validator"
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzzabe6f9r3fwtbd3w4tddqy
created_at: 2026-08-14T05:02:01.739Z
updated_at: 2026-08-14T05:02:16.812Z
---
PR #40 comment 5289663054, R7. wire_models.py hardcodes 20 rather than using the rollup fallback limits. Establish one source of truth and test limit drift.
