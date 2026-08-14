---
type: is
id: is-01kzzac0pjm45aphk5mdzz7ecg
title: "PR #40 review R2: surface Overview registry contract errors"
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01kzzabe6f9r3fwtbd3w4tddqy
created_at: 2026-08-14T05:02:00.401Z
updated_at: 2026-08-14T05:25:15.770Z
closed_at: 2026-08-14T05:25:15.769Z
close_reason: "Fixed: rollup normalization and model construction are transactional; incompatible first data renders a terminal contract error instead of leaving a skeleton."
---
PR #40 comment 5289663054, R2. file_type_summary.js/inventory_scope.js: registry mismatch and malformed breakdown errors are swallowed behind a permanent loading skeleton. Provide explicit fallback or user-visible error with regression coverage.
