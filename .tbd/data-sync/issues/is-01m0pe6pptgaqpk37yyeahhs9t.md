---
type: is
id: is-01m0pe6pptgaqpk37yyeahhs9t
title: "H50: reserve the height of regions rendered before their content"
kind: task
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-23T04:31:32.569Z
updated_at: 2026-08-23T04:32:00.183Z
closed_at: 2026-08-23T04:32:00.182Z
close_reason: "exp-009: filter bar 24px -> 0, tally row 18px -> 0, total 42px -> 0 on the official corpus at 1280x900. Both reserve a derived height rather than a measured one, so a font-set change cannot drift them."
---
RESOLVED by exp-009. The filter bar (shipped empty, filled by JS: 13px -> 37px) and the tally row (painted with inlined rows, numbers arrive later: 13px -> 31px) grew under the reader on every load. Both now reserve their settled height via a derived --chip-height token. 42px -> 0.
