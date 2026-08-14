---
type: is
id: is-01kzzac1798e9wtf42srmt2823
title: "PR #40 review R4: make fallback type semantics consistent"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzzabe6f9r3fwtbd3w4tddqy
created_at: 2026-08-14T05:02:00.936Z
updated_at: 2026-08-14T05:25:16.485Z
closed_at: 2026-08-14T05:25:16.484Z
close_reason: "Fixed: removed the legacy Files-summary projection, so Other types has one Breakdown v1 meaning; remaining_types remains the explicit wire member."
---
PR #40 comment 5289663054, R4. Breakdown and legacy fallback paths use the fallback label for different populations. Make the retained behavior and label semantics consistent, or remove the unreachable fallback.
